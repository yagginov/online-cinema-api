from typing import Annotated, Sequence

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models import CertificationModel, DirectorModel, GenreModel, MovieModel, StarModel
from filters.movie_filters import MovieSearchParams
from services.movie_filter_service import MovieSearchService

from ..generic import AsyncRepository
from .certifications import CertificationRepository
from .directors import DirectorRepository
from .genres import GenreRepository
from .stars import StarRepository


class MovieRepository(AsyncRepository[MovieModel]):
    async def create_object(self, data: dict | BaseModel, *, flush_only: bool = False) -> MovieModel:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        certification = data.pop("certification", None)
        if not certification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create movie without certification",
            )
        genres = set(data.pop("genres", []))
        if not genres:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create movie without genres",
            )
        stars = set(data.pop("stars", []))
        if not stars:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create movie without stars",
            )
        directors = set(data.pop("directors", []))
        if not directors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create movie without directors",
            )

        certification_repo = CertificationRepository(CertificationModel, self.session)
        genre_repo = GenreRepository(GenreModel, self.session)
        star_repo = StarRepository(StarModel, self.session)
        director_repo = DirectorRepository(DirectorModel, self.session)

        certification_obj, _ = await certification_repo.get_or_create(flush_only=True, name=certification)
        genre_objs = [(await genre_repo.get_or_create(flush_only=True, name=genre))[0] for genre in genres]
        star_objs = [(await star_repo.get_or_create(flush_only=True, name=star))[0] for star in stars]
        director_objs = [
            (await director_repo.get_or_create(flush_only=True, name=director))[0] for director in directors
        ]

        obj = self.model(
            certification=certification_obj,
            genres=genre_objs,
            stars=star_objs,
            directors=director_objs,
            **data,
        )
        self.session.add(obj)
        try:
            await self.session.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Somethings went wrong",
            )
        await self.session.refresh(obj)
        return obj

    async def update_object(self, data: dict | BaseModel, **filters) -> MovieModel:
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_unset=True)

        movie = await self.get_object_or_404(**filters)

        certification = data.pop("certification", None)
        genres = data.pop("genres", None)
        stars = data.pop("stars", None)
        directors = data.pop("directors", None)

        certification_repo = CertificationRepository(CertificationModel, self.session)
        genre_repo = GenreRepository(GenreModel, self.session)
        star_repo = StarRepository(StarModel, self.session)
        director_repo = DirectorRepository(DirectorModel, self.session)

        for key, value in data.items():
            setattr(movie, key, value)

        if certification is not None:
            certification_obj, _ = await certification_repo.get_or_create(flush_only=True, name=certification)
            movie.certification = certification_obj

        if genres is not None:
            genre_objs = [(await genre_repo.get_or_create(flush_only=True, name=genre))[0] for genre in set(genres)]
            movie.genres = genre_objs

        if stars is not None:
            star_objs = [(await star_repo.get_or_create(flush_only=True, name=star))[0] for star in set(stars)]
            movie.stars = star_objs

        if directors is not None:
            director_objs = [
                (await director_repo.get_or_create(flush_only=True, name=director))[0] for director in set(directors)
            ]
            movie.directors = director_objs

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update movie due to integrity error",
            )

        await self.session.refresh(movie)
        return movie

    async def get_object(self, **filters) -> MovieModel | None:
        stmt = (
            select(self.model)
            .filter_by(**filters)
            .options(
                joinedload(self.model.certification),
                joinedload(self.model.genres),
                joinedload(self.model.stars),
                joinedload(self.model.directors),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_objects(
        self,
        *,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 100,
        ordering: list[str] | None = None,
    ) -> Sequence[MovieModel]:
        stmt = select(self.model).options(joinedload(self.model.certification))
        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = self._apply_ordering(stmt, ordering)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_movies(
        self, search_params: MovieSearchParams, load_relationships: bool = True
    ) -> tuple[list[MovieModel], int]:

        return await MovieSearchService.search_movies(
            db=self.session, search_params=search_params, load_relationships=load_relationships
        )


async def get_movie_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MovieRepository:
    return MovieRepository(MovieModel, db)
