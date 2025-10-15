from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from enums.payment_enums import PaymentSortByEnum, PaymentStatus

from .base import BasePaginationParams, BaseSortParams, SortOrderEnum


class PaymentFilterParams(BasePaginationParams, BaseSortParams):
    status: Optional[PaymentStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    user_id: Optional[int] = Field(default=None, ge=1)
    sort_by: PaymentSortByEnum = Field(default=PaymentSortByEnum.CREATED_AT)

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):  # noqa: ANN001
        return v

    def get_ordering(self) -> list[str]:
        field = self.sort_by.value
        prefix = "-" if self.sort_order == SortOrderEnum.DESC else ""
        return [f"{prefix}{field}"]
