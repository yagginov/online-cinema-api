from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from database.models import MovieModel

router = APIRouter()


@router.get(
    "/movies/",
)
async def get_movies(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    movies = await db.scalars(
        select(MovieModel)
        .limit(100)
    )
    return movies.all()
