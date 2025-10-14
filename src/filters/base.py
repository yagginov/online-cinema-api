from enum import Enum

from pydantic import BaseModel, Field


class SortOrderEnum(str, Enum):
    ASC = "asc"
    DESC = "desc"


class BasePaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=50)

    def get_offset(self) -> int:
        return (self.page - 1) * self.per_page


class BaseSortParams(BaseModel):
    sort_order: SortOrderEnum = Field(default=SortOrderEnum.DESC)
