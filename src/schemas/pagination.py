import math
from typing import Generic, Sequence, TypeVar

from pydantic import AnyUrl, BaseModel, computed_field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    page: int
    size: int
    total_items: int
    total_pages: int
    prev_page: AnyUrl | None
    next_page: AnyUrl | None
