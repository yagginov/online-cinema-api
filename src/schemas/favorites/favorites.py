from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict

from ..accounts.accounts import MessageResponseSchema
from ..movies.movies import MovieListItemSchema
from ..pagination import PaginatedResponse


class FavoriteItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie: MovieListItemSchema
    created_at: datetime


class FavoriteBaseResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
    created_at: datetime


class FavoriteAddResponseSchema(FavoriteBaseResponseSchema):
    pass


class FavoriteDeleteResponseSchema(MessageResponseSchema):
    pass


FavoritesPaginatedResponseSchema: TypeAlias = PaginatedResponse[FavoriteItemSchema]
