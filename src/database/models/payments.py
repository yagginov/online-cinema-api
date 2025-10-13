from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DECIMAL, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from enums.payment_enums import PaymentStatus


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), nullable=False, default=PaymentStatus.SUCCESSFUL
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    items: Mapped[list["PaymentItemModel"]] = relationship(
        "PaymentItemModel", back_populates="payment", cascade="all, delete-orphan"
    )
    order = relationship("OrderModel")
    user = relationship("User", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_status", "status"),
        Index("ix_payments_ext_id", "external_payment_id"),
    )

    def __repr__(self):
        return f"<Payment(id={self.id}, order_id={self.order_id}, status={self.status}, amount={self.amount})>"


class PaymentItemModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    price_at_payment: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)

    payment: Mapped[PaymentModel] = relationship("PaymentModel", back_populates="items")
    order_item = relationship("OrderItemModel")

    __table_args__ = (UniqueConstraint("payment_id", "order_item_id", name="uq_payment_item"),)

    def __repr__(self):
        return (
            f"<PaymentItem(payment_id={self.payment_id}, "
            f"order_item_id={self.order_item_id}, price={self.price_at_payment})>"
        )
