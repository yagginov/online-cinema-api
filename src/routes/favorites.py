import math
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AnyUrl

from database.models.accounts import User
from repositories.favorites.favorites import FavoriteRepository, get_favorite_repository
from schemas.favorites import (
    FavoriteAddResponseSchema,
    FavoriteDeleteResponseSchema,
    FavoriteItemSchema,
    FavoritesPaginatedResponseSchema,
)
from schemas.movies import MovieListItemSchema
from security.permissions import get_current_user

router = APIRouter()


@router.post(
    "/favorites/{movie_id}/",
    response_model=FavoriteAddResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add movie to favorites",
    description="Add a movie to the authenticated user's favorites list",
)
async def add_to_favorites(
    movie_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):

    favorite = await favorite_repo.add_to_favorites(user_id=current_user.id, movie_id=movie_id)
    return FavoriteAddResponseSchema.model_validate(favorite)


@router.delete(
    "/favorites/{movie_id}/",
    response_model=FavoriteDeleteResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Remove movie from favorites",
    description="Delete a movie from the authenticated user's favorites list",
)
async def delete_from_favorites(
    movie_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):
    await favorite_repo.remove_from_favorites(user_id=current_user.id, movie_id=movie_id)

    return FavoriteDeleteResponseSchema(message="Movie removed from favorites successfully")


@router.get(
    "/favorites/",
    response_model=FavoritesPaginatedResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get user's favorite movies",
    description="Retrieve a paginated list of the authenticated user's favorite movies (maybe add pagination)",
)
async def get_favorites(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):
    favorites = await favorite_repo.get_user_favorites(
        user_id=current_user.id,
        offset=(page - 1) * size,
        limit=size,
    )

    total = await favorite_repo.get_user_favorites_count(user_id=current_user.id)

    total_pages = math.ceil(total / size) if total > 0 else 1

    next_page = AnyUrl(str(request.url.replace_query_params(page=page + 1, size=size))) if page < total_pages else None
    prev_page = AnyUrl(str(request.url.replace_query_params(page=page - 1, size=size))) if page > 1 else None

    items = [
        FavoriteItemSchema(
            id=favorite.id,
            movie=MovieListItemSchema.model_validate(favorite.movie),
            created_at=favorite.created_at,
        )
        for favorite in favorites
    ]

    return FavoritesPaginatedResponseSchema(
        items=items,
        page=page,
        size=size,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )
