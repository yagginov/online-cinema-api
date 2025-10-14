from typing import List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models.movies import MovieModel, GenreModel
from filters.movie_filters import MovieFilterParams, MovieSortByEnum, SortOrderEnum


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
                stmt = stmt.where(
                    MovieModel.genres.any(GenreModel.id == genre_id)
                )
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
    async def get_filtered_movies(
        db: AsyncSession,
        filters: MovieFilterParams,
        load_relationships: bool = True
    ) -> Tuple[List[MovieModel], int]:

        filters.validate_ranges()
        base_stmt = select(MovieModel)
        filtered_stmt = MovieFilterService.apply_filters(base_stmt, filters)

        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        result_count = await db.execute(count_stmt)
        total_items = result_count.scalar() or 0

        sorted_stmt = MovieFilterService.apply_sorting(
            filtered_stmt,
            filters.sort_by,
            filters.sort_order,
        )

        offset = filters.get_offset()
        paginated_stmt = sorted_stmt.offset(offset).limit(filters.per_page)

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
