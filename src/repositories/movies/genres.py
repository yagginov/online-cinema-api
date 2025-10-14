from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from database.models import GenreModel
from repositories.generic import AsyncRepository


class GenreRepository(AsyncRepository[GenreModel]):
    pass


async def get_genre_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return GenreRepository(GenreModel, db)
