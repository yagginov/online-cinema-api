from typing import Annotated, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from database.models import MovieModel
from database.models.favorites import FavoriteModel

from ..generic import AsyncRepository


class FavoriteRepository(AsyncRepository[FavoriteModel]):

    async def add_to_favorites(self, user_id: int, movie_id: int) -> FavoriteModel:

        if await self.is_exist(user_id=user_id, movie_id=movie_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot add the same movie twice")

        movie_stmt = select(MovieModel).where(MovieModel.id == movie_id)
        movie_result = await self.session.execute(movie_stmt)
        movie = movie_result.scalars().first()

        if not movie:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The film must exist")

        return await self.create_object({"user_id": user_id, "movie_id": movie_id})

    async def remove_from_favorites(self, user_id: int, movie_id: int) -> bool:
        favorite = await self.get_object(user_id=user_id, movie_id=movie_id)

        if not favorite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Movie with id {movie_id} is not in your favorites"
            )

        return await self.delete_object(user_id=user_id, movie_id=movie_id)

    async def get_user_favorites(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
        ordering: list[str] | None = None,
    ) -> Sequence[FavoriteModel]:
        stmt = (
            select(self.model)
            .options(
                selectinload(FavoriteModel.movie).selectinload(MovieModel.genres),
                selectinload(FavoriteModel.movie).selectinload(MovieModel.certification),
            )
            .filter_by(user_id=user_id)
        )

        if ordering is None:
            ordering = ["-created_at"]

        stmt = self._apply_ordering(stmt, ordering)
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_user_favorites_count(self, user_id: int) -> int:
        return await self.get_total(filters={"user_id": user_id})


async def get_favorite_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FavoriteRepository:
    return FavoriteRepository(FavoriteModel, db)