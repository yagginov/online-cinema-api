from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from database.models import DirectorModel
from repositories.generic import AsyncRepository


class DirectorRepository(AsyncRepository[DirectorModel]):
    pass


async def get_director_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return DirectorRepository(DirectorModel, db)
