from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class BaseInteraction(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class FavoriteModel(BaseInteraction):
    __tablename__ = "favorites"

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="movie_favorite"),)

    def __repr__(self):
        return f"<Favorite(user_id='{self.user_id}', movie_id='{self.movie_id}')>"


class RatingModel(BaseInteraction):
    __tablename__ = "ratings"

    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="movie_rating"),
        CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
    )

    def __repr__(self) -> str:
        return f"<Rating(user_id={self.user_id}, movie_id={self.movie_id}, rating={self.rating})>"


class CommentModel(BaseInteraction):
    __tablename__ = "comments"

    text: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    replies = relationship(
        "CommentModel",
        cascade="all, delete-orphan",
        back_populates="parent",
    )
    parent = relationship("CommentModel", remote_side="CommentModel.id", back_populates="replies")

    def __repr__(self) -> str:
        return f"<Comment user_id={self.user_id}, movie_id={self.movie_id}, text={self.text[:30]}>"


class CommentLikeModel(Base):
    __tablename__ = "comment_likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_like: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "comment_id", name="uq_user_comment_like"),)

    def __repr__(self) -> str:
        return f"<CommentLike user_id={self.user_id}, comment_id={self.comment_id}, is_like={self.is_like}>"