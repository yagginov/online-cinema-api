from typing import List, Tuple

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from database.models.movies import GenreModel, MovieModel, StarModel, DirectorModel
from filters.movie_filters import MovieFilterParams, MovieSortByEnum, SortOrderEnum, MovieSearchParams


class MovieFilterService:
    @staticmethod
    def apply_filters(stmt, filters: MovieFilterParams):
        if filters.year_from:
            stmt = stmt.where(MovieModel.year >= filters.year_from)
        if filters.year_to:
            stmt = stmt.where(MovieModel.year <= filters.year_to)

        if filters.min_imdb is not None:
            stmt = stmt.where(MovieModel.imdb >= filters.min_imdb)
        if filters.max_imdb is not None:
            stmt = stmt.where(MovieModel.imdb <= filters.max_imdb)

        if filters.certification_id:
            stmt = stmt.where(MovieModel.certification_id == filters.certification_id)

        genre_ids = filters.get_genre_ids_list()
        if genre_ids:
            for genre_id in genre_ids:
                stmt = stmt.where(MovieModel.genres.any(GenreModel.id == genre_id))
        return stmt

    @staticmethod
    def apply_sorting(stmt, sort_by: MovieSortByEnum, sort_order: SortOrderEnum):
        sort_field_map = {
            MovieSortByEnum.PRICE: MovieModel.price,
            MovieSortByEnum.YEAR: MovieModel.year,
            MovieSortByEnum.IMDB: MovieModel.imdb,
            MovieSortByEnum.VOTES: MovieModel.votes,
            MovieSortByEnum.NAME: MovieModel.name,
        }

        field = sort_field_map[sort_by]

        if sort_order == SortOrderEnum.ASC:
            stmt = stmt.order_by(field.asc())
        else:
            stmt = stmt.order_by(field.desc())

        return stmt

    @staticmethod
    async def _execute_paginated_query(
        db: AsyncSession,
        filtered_stmt: Select,
        page: int,
        per_page: int,
        sort_by: MovieSortByEnum,
        sort_order: SortOrderEnum,
        load_relationships: bool = True,
    ) -> Tuple[List[MovieModel], int]:
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        result_count = await db.execute(count_stmt)
        total_items = result_count.scalar() or 0

        sorted_stmt = MovieFilterService.apply_sorting(
            filtered_stmt,
            sort_by,
            sort_order,
        )

        offset = (page - 1) * per_page
        paginated_stmt = sorted_stmt.offset(offset).limit(per_page)

        if load_relationships:
            paginated_stmt = paginated_stmt.options(
                joinedload(MovieModel.certification),
                joinedload(MovieModel.genres),
                joinedload(MovieModel.stars),
                joinedload(MovieModel.directors),
            )

        result = await db.execute(paginated_stmt)
        movies = result.unique().scalars().all()

        return list(movies), total_items

    @staticmethod
    async def get_filtered_movies(
        db: AsyncSession,
        filters: MovieFilterParams,
        load_relationships: bool = True,
    ) -> Tuple[List[MovieModel], int]:
        filters.validate_ranges()

        base_stmt = select(MovieModel)
        filtered_stmt = MovieFilterService.apply_filters(base_stmt, filters)

        return await MovieFilterService._execute_paginated_query(
            db=db,
            filtered_stmt=filtered_stmt,
            page=filters.page,
            per_page=filters.per_page,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            load_relationships=load_relationships,
        )


class MovieSearchService:

    @staticmethod
    def apply_search_filters(stmt, search_params: MovieSearchParams):

        if search_params.title:
            stmt = stmt.where(
                MovieModel.name.ilike(f"%{search_params.title}%")
            )

        if search_params.description:
            stmt = stmt.where(
                MovieModel.description.ilike(f"%{search_params.description}%")
            )

        star_names = search_params.get_star_names_list()
        if star_names:
            star_conditions = [
                MovieModel.stars.any(StarModel.name.ilike(f"%{name}%"))
                for name in star_names
            ]
            stmt = stmt.where(or_(*star_conditions))

        director_names = search_params.get_director_names_list()
        if director_names:
            director_conditions = [
                MovieModel.directors.any(DirectorModel.name.ilike(f"%{name}%"))
                for name in director_names
            ]
            stmt = stmt.where(or_(*director_conditions))

        return stmt

    @staticmethod
    async def search_movies(
        db: AsyncSession,
        search_params: MovieSearchParams,
        load_relationships: bool = True,
    ) -> Tuple[List[MovieModel], int]:

        base_stmt = select(MovieModel)
        filtered_stmt = MovieSearchService.apply_search_filters(base_stmt, search_params)

        return await MovieFilterService._execute_paginated_query(
            db=db,
            filtered_stmt=filtered_stmt,
            page=search_params.page,
            per_page=search_params.per_page,
            sort_by=search_params.sort_by,
            sort_order=search_params.sort_order,
            load_relationships=load_relationships,
        )
