from decimal import Decimal
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..pagination import PaginatedResponse
from .certifications import CertificationSchema
from .directors import DirectorSchema
from .genres import GenreSchema
from .stars import StarSchema


class MovieBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None
    gross: float | None
    description: str
    price: Decimal = Field(..., examples=[Decimal("12.35")])


class MovieListItemSchema(MovieBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    certification: CertificationSchema

    @field_serializer("certification")
    def serialize_certification(self, certification_obj: CertificationSchema, _info) -> str | None:
        return getattr(certification_obj, "name", None)


MoviePaginatedResponseSchema: TypeAlias = PaginatedResponse[MovieListItemSchema]


class MovieDetailResponseSchema(MovieBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    certification: CertificationSchema
    directors: list[DirectorSchema]
    stars: list[StarSchema]
    genres: list[GenreSchema]


class MovieCreateRequestSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None
    gross: float | None
    description: str
    price: Decimal = Field(..., examples=[Decimal("12.35")])
    certification: str
    directors: list[str]
    stars: list[str]
    genres: list[str]


class MovieUpdateRequestSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    year: int | None = None
    time: int | None = None
    imdb: float | None = None
    votes: int | None = None
    meta_score: float | None = None
    gross: float | None = None
    description: str | None = None
    price: Decimal | None = Field(None, examples=[Decimal("12.35")])
    certification: str | None = None
    directors: list[str] | None = None
    stars: list[str] | None = None
    genres: list[str] | None = None
