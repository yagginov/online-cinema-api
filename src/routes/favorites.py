import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AnyUrl

from config.dependencies import get_jwt_auth_manager
from exceptions import BaseSecurityError
from repositories.favorites.favorites import (
    FavoriteRepository,
    get_favorite_repository
)
from schemas.favorites import (
    FavoriteAddResponseSchema,
    FavoriteDeleteResponseSchema,
    FavoriteItemSchema,
    FavoritesPaginatedResponseSchema,
)
from schemas.movies import MovieListItemSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


async def get_current_user_id(
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id not found"
            )
        return user_id
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post(
    "/api/v1/favorites/{movie_id}/",
    response_model=FavoriteAddResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add movie to favorites",
    description="Add a movie to the authenticated user's favorites list",
)
async def add_to_favorites(
        movie_id: int,
        user_id: int = Depends(get_current_user_id),
        favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):

    favorite = await favorite_repo.add_to_favorites(user_id=user_id, movie_id=movie_id)
    return FavoriteAddResponseSchema.model_validate(favorite)


@router.delete(
    "/api/v1/favorites/{movie_id}/",
    response_model=FavoriteDeleteResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Remove movie from favorites",
    description="Delete a movie from the authenticated user's favorites list",
)
async def delete_from_favorites(
        movie_id: int,
        user_id: int = Depends(get_current_user_id),
        favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):
    await favorite_repo.remove_from_favorites(user_id=user_id, movie_id=movie_id)

    return FavoriteDeleteResponseSchema(
        message="Movie removed from favorites successfully"
    )


@router.get(
    "/api/v1/favorites/",
    response_model=FavoritesPaginatedResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get user's favorite movies",
    description="Retrieve a paginated list of the authenticated user's favorite movies (maybe add pagination)",
)
async def get_favorites(
        request: Request,
        user_id: int = Depends(get_current_user_id),
        page: Annotated[int, Query(ge=1)] = 1,
        size: Annotated[int, Query(ge=1, le=50)] = 20,
        favorite_repo: FavoriteRepository = Depends(get_favorite_repository),
):
    favorites = await favorite_repo.get_user_favorites(
        user_id=user_id,
        offset=(page - 1) * size,
        limit=size,
    )

    total = await favorite_repo.get_user_favorites_count(user_id=user_id)

    total_pages = math.ceil(total / size) if total > 0 else 1

    next_page = (
        AnyUrl(str(request.url.replace_query_params(page=page + 1, size=size)))
        if page < total_pages
        else None
    )
    prev_page = (
        AnyUrl(str(request.url.replace_query_params(page=page - 1, size=size)))
        if page > 1
        else None
    )

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