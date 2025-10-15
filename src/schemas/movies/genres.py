from pydantic import AnyUrl, BaseModel, ConfigDict


class GenreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class GenreResponseSchema(GenreSchema):
    movies_url: AnyUrl
