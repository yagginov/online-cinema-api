from datetime import datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, func, Enum, DECIMAL, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from enums.order_enums import OrderStatus


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status"), nullable=False,
                                                default=OrderStatus.PENDING)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=True)
    items: Mapped[list["OrderItemModel"]] = relationship(":OrderItemModel", back_populates="order",
                                                         cascade="all, delete-orphan")
    user = relationship("User", back_populates="orders")
    __table_args__ = (
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, user_id={self.user_id}, status={self.status})>"


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="RESTRICT"), index=True, nullable=False)
    price_at_order: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="items")
    movie = relationship("MovieModel")

    __table_args__ = (
        UniqueConstraint("order_id", "movie_id", name="uniq_order_item"),
    )

    def __repr__(self) -> str:
        return f"<OrderItem(order_id={self.order_id}, movie_id={self.movie_id}, price={self.price_at_order})>"

