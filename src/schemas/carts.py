from decimal import Decimal
from typing import List

from pydantic import BaseModel, field_validator


class CartRequestSchema(BaseModel):
    user__id: int


class CartListItemSchema(BaseModel):
    id: int
    name: str
    price: Decimal
    genres: str
    year: int

    model_config = {"from_attributes": True}

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        return Decimal(v)

    @field_validator("genres")
    @classmethod
    def validate_genres(cls, v):
        if isinstance(v, list):
            return ", ".join([g.name for g in v])
        return v


class CartResponseSchema(BaseModel):
    id: int
    movies: list[CartListItemSchema]

    class Config:
        orm_mode = True


class CartItemAddRequestSchema(BaseModel):
    movie_id: int


class CartItemAddResponseSchema(BaseModel):
    id: int
    movies: list[CartListItemSchema]


class CartItemRemoveRequestSchema(BaseModel):
    user_id: int
    movie_id: int


class CartDeleteRequestSchema(BaseModel):
    user_id: int


class CartDeleteResponseSchema(BaseModel):
    user_id: int


class CartListRequestSchema(BaseModel):
    user_id: int


class CartListResponseSchema(BaseModel):
    items: List[CartListItemSchema]
