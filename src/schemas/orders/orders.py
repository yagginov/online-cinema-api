from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from ..pagination import PaginatedResponse


class OrderItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    movie_id: int
    price_at_order: Decimal = Field(..., examples=[Decimal("9.99")])


class OrderResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: str
    total_amount: Decimal = Field(..., examples=[Decimal("19.98")])
    created_at: datetime
    items: list[OrderItemResponseSchema]


class OrderCreateRequestSchema(BaseModel):
    movie_ids: list[int] = Field(..., min_length=1, description="List of movie IDs to include in the order")


OrderPaginatedResponseSchema: TypeAlias = PaginatedResponse[OrderResponseSchema]
