from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import AnyUrl

from repositories.movies import GenreRepository, get_genre_repository
from schemas.movies import GenreResponseSchema

router = APIRouter()


@router.get(
    "/genres/",
)
async def get_genres(
    request: Request,
    genre_repo: Annotated[GenreRepository, Depends(get_genre_repository)],
) -> list[GenreResponseSchema]:
    genres = await genre_repo.get_objects_or_404(limit=1000000)
    return [
        GenreResponseSchema(
            id=genre.id,
            name=genre.name,
            movies_url=AnyUrl(f"{str(request.url).replace("genres", "movies").rstrip("/")}/?genre_ids={genre.id}"),
        )
        for genre in genres
    ]
