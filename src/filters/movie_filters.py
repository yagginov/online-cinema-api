from enum import Enum
from typing import List, Optional

from fastapi import HTTPException, status
from pydantic import Field, field_validator

from .base import BasePaginationParams, BaseSortParams, SortOrderEnum


class MovieSortByEnum(str, Enum):
    PRICE = "price"
    YEAR = "year"
    IMDB = "imdb"
    VOTES = "votes"
    NAME = "name"


class MovieFilterParams(BasePaginationParams, BaseSortParams):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "page": 1,
                    "per_page": 10,
                    "year_from": 2020,
                    "year_to": 2024,
                    "min_imdb": 7.0,
                    "max_imdb": 10.0,
                    "min_price": 5.99,
                    "max_price": 19.99,
                    "genre_ids": "1,2,5",
                    "certification_id": 3,
                    "sort_by": "imdb",
                    "sort_order": "desc",
                }
            ]
        }
    }

    year_from: Optional[int] = Field(None, ge=1900, le=2100)
    year_to: Optional[int] = Field(None, ge=1900, le=2100)

    min_imdb: Optional[float] = Field(None, ge=0.0, le=10.0)
    max_imdb: Optional[float] = Field(None, ge=0.0, le=10.0)

    min_price: Optional[float] = Field(None, ge=0.0)
    max_price: Optional[float] = Field(None, ge=0.0)

    genre_ids: Optional[str] = None
    certification_id: Optional[int] = Field(None, ge=1)

    sort_by: MovieSortByEnum = Field(default=MovieSortByEnum.IMDB)

    @field_validator("year_from", "year_to")
    @classmethod
    def validate_years(cls, value):
        if value and (value < 1900 or value > 2100):
            raise ValueError("Year must be between 1900 and 2100")
        return value

    @field_validator("min_imdb", "max_imdb")
    @classmethod
    def validate_imdb(cls, value):
        if value is not None and (value < 0.0 or value > 10.0):
            raise ValueError("IMDb rating must be between 0.0 and 10.0")
        return value

    def get_genre_ids_list(self) -> Optional[List[int]]:
        if not self.genre_ids:
            return None
        try:
            return [int(gid.strip()) for gid in self.genre_ids.split(",") if gid.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="genre_ids must contain comma-separated integers",
            )

    def validate_ranges(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="year_from cannot be greater than year_to"
            )

        if self.min_imdb and self.max_imdb and self.min_imdb > self.max_imdb:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="min_imdb cannot be greater than max_imdb"
            )

        if self.min_price and self.max_price and self.min_price > self.max_price:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="min_price cannot be greater than max_price"
            )


class MovieSearchParams(BasePaginationParams):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    star_names: Optional[str] = Field(None, description="Comma-separated star names")
    director_names: Optional[str] = Field(None, description="Comma-separated director names")

    sort_by: MovieSortByEnum = Field(default=MovieSortByEnum.IMDB)
    sort_order: SortOrderEnum = Field(default=SortOrderEnum.DESC)

    def get_star_names_list(self) -> Optional[List[str]]:
        if not self.star_names:
            return None
        return [name.strip() for name in self.star_names.split(",") if name.strip()]

    def get_director_names_list(self) -> Optional[List[str]]:
        if not self.director_names:
            return None
        return [name.strip() for name in self.director_names.split(",") if name.strip()]
