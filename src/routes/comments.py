from typing import Annotated

from fastapi import (
    APIRouter,
    status, Depends, HTTPException,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from database.models import MovieModel
from database.models.comments import CommentModel

from schemas.errors import NotFoundErrorResponse
from schemas.movies.comments import CommentCreateRequestSchema, \
    CommentCreateResponseSchema, CommentListResponseSchema, \
    CommentListItemSchema, CommentListRequestSchema

router = APIRouter()

@router.post(
    "/movies/{movie_id}/comments/",
    response_model=CommentCreateResponseSchema,
    description="Add a comment under the movie",
    status_code=201,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie with this id not found",
            "model": NotFoundErrorResponse,
            "content": {
                "application/json": {
                    "example": NotFoundErrorResponse(
                        detail="Movie with this id not found"),
                },
            },
        },
    },
)
async def create_comment(
        movie_id: int,
        comment_data: CommentCreateRequestSchema,
        db: AsyncSession = Depends(get_db)):
    user_stmt = select(User).where(User.id == comment_data.user_id)
    user_result = await db.execute(user_stmt)

    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please register or log in to add movies to access your cart.",
        )

    movie_stmt = select(MovieModel).where(MovieModel.id == movie_id)
    movie_result = await db.execute(movie_stmt)

    movie = movie_result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with this id not found",
        )

    comment = CommentModel(
        text=comment_data.text,
        parent_id=movie_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentCreateResponseSchema.model_validate(comment)


@router.get("/movies/{movie_id}/comments/",
    response_model=CommentListResponseSchema,
    description="View comments under the movie",
    status_code=200,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie with this id not found",
            "model": NotFoundErrorResponse,
            "content": {
                "application/json": {
                    "example": NotFoundErrorResponse(
                        detail="Movie with this id not found"),
                },
            },
        },
    },
)
async def get_comments(
        movie_id: int,
        comment_data: CommentListRequestSchema,
        db: AsyncSession = Depends(get_db)
):
    user_stmt = select(User).where(User.id == comment_data.user_id)
    user_result = await db.execute(user_stmt)

    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please register or log in to add movies to access your cart.",
        )

    movie_stmt = select(MovieModel).where(MovieModel.id == movie_id)
    movie_result = await db.execute(movie_stmt)

    movie = movie_result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with this id not found",
        )

    comments_stmt = select(CommentModel).where(CommentModel.movie_id == movie_id)
    comments_result = await db.execute(comments_stmt)

    comments = comments_result.scalars().all()

    if not comments:
        return CommentListResponseSchema(comments=[])

    comments_list = [CommentListItemSchema.model_validate(comment) for comment in comments]

    return CommentListResponseSchema(comments=comments_list)
