from datetime import datetime
from decimal import Decimal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from enums.payment_enums import PaymentStatus
from .pagination import PaginatedResponse


class PaymentCreateRequestSchema(BaseModel):
    order_id: int = Field(..., description="ID of the order to pay for")


class PaymentCreateResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    status: PaymentStatus
    amount: Decimal = Field(..., examples=[Decimal("19.98")])
    created_at: datetime
    payment_url: AnyUrl


class PaymentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    user_id: int
    status: PaymentStatus
    amount: Decimal
    created_at: datetime


PaymentPaginatedResponseSchema = PaginatedResponse[PaymentResponseSchema]
