from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .accounts import User
from .base import Base
from .movies import MovieModel


class FavoriteModel(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", backref="favorites")
    movie: Mapped["MovieModel"] = relationship("MovieModel", backref="favorited_by")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="unique_user_movie_favorite"),)

    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, movie_id={self.movie_id})>"
