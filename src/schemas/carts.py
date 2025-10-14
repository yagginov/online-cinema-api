from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from database.models import MovieModel


class CartRequestSchema(BaseModel):
    cart_id: int

class CartResponseSchema(BaseModel):
    id: int
    movies: list[MovieModel]

    class Config:
        orm_mode = True

class CartItemAddRequestSchema(BaseModel):
    cart_id: int
    movie_id: int

class CartItemAddResponseSchema(BaseModel):
    id: int
    movies: list[MovieModel]
