import datetime

from sqlalchemy import (
    ForeignKey,
    func,
    DateTime, UniqueConstraint,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database.models.base import Base


class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id",
        ondelete="CASCADE"), nullable=False, unique=True
    )
    user = relationship("User")
    items: Mapped[list["CartItemModel"]] = relationship(
        "CartItemModel",
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<cart id: {self.id}, user id: {self.user_id}>"



class CartItemModel(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id",
        ondelete="CASCADE"), nullable=False
        )
    cart = relationship("CartModel", back_populates="items")
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", name="uq_cart_movie"),
    )

    def __repr__(self):
        return f"<item id: {self.id}, cart id: {self.cart_id}>"
