from fastapi import (
    APIRouter,
    status, Depends, HTTPException,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from database.models import MovieModel
from database.models.comments import CommentModel

from schemas.movies.comments import (
    CommentCreateRequestSchema,
    CommentCreateResponseSchema,
    CommentListResponseSchema,
    CommentListItemSchema,
    CommentListRequestSchema,
    CommentReplyCreateRequestSchema,
    CommentReplyCreateResponseSchema,
    CommentReplyUpdateResponseSchema,
    CommentReplyUpdateRequestSchema
)
from security.permissions import get_current_user

router = APIRouter()

@router.post(
    "/movies/{movie_id}/comments/",
    response_model=CommentCreateResponseSchema,
    description="Add a comment under the movie",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with given id not found."
                    }
                },
            },
        },
    },
    status_code=201,
)
async def create_comment(
        movie_id: int,
        comment_data: CommentCreateRequestSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
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
        user_id=current_user.id,
        movie_id=movie_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentCreateResponseSchema.model_validate(comment)


@router.get("/movies/{movie_id}/comments/",
    response_model=CommentListResponseSchema,
    description="View comments under the movie",
    status_code=200,
)
async def get_comments(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
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

@router.get(
    "/comments/{comment_id}/reply/",
    response_model=CommentReplyCreateResponseSchema,
    description="Allows users create replies to other comments",
    status_code=201,
)
async def create_comment_reply(
        comment_id: int,
        comment_reply_data: CommentReplyCreateRequestSchema,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user),
):
    comment_stmt = select(CommentModel).where(CommentModel.id==comment_id)
    comment_result = await db.execute(comment_stmt)

    comment = comment_result.scalars().first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment with given id not found",
        )

    comment_reply = CommentModel(
        text=comment_reply_data.text,
        movie_id=comment.movie_id,
        user_id=user.id,
        parent_id=comment_id,
    )

    db.add(comment_reply)
    await db.commit()
    await db.refresh(comment_reply)

    return CommentReplyCreateResponseSchema.model_validate(comment_reply)


@router.put(
    "/comments/{comment_id}/",
    status_code=status.HTTP_200_OK,
    response_model=CommentReplyUpdateResponseSchema,
    description="Update text of your comment. Allowed only for author of the comment",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "User is not the author of the comment.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Only auther can edit their comment"
                    }
                },
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Comment with given id not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Comment with given id not found."
                    }
                },
            },
        },
    },
)
async def update_comment(
        comment_id: int,
        new_data: CommentReplyUpdateRequestSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    comment_stmt = select(CommentModel).where(CommentModel.id == comment_id)
    comment_result = await db.execute(comment_stmt)

    comment = comment_result.scalars().first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment with given id not found",
        )

    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only auther can edit their comment",
        )

    comment.text = new_data.text

    await db.commit()
    await db.refresh(comment)

    return CommentReplyUpdateResponseSchema(comment)

@router.delete(
    "/comments/{comment_id}/",
    description="Delete comment, allowed only for author of the comment",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "User is not the author of the comment.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Only auther can delete their comment"
                    }
                },
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Comment with given id not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Comment with given id not found."
                    }
                },
            },
        },
    },
)
async def delete_comment(
        comment_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    comment_stmt = select(CommentModel).where(CommentModel.id == comment_id)
    comment_result = await db.execute(comment_stmt)

    comment = comment_result.scalars().first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment with given id not found",
        )

    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only auther can delete their comment",
        )

    await db.delete(comment)
    await db.commit()
