from datetime import datetime

from pydantic import BaseModel

from database.models.comments import CommentModel


class CommentCreateRequestSchema(BaseModel):
    user_id: int
    movie_id: int
    text: str

class CommentCreateResponseSchema(BaseModel):
    id: int
    text: str
    movie_id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class CommentListItemSchema(BaseModel):
    id: int
    text: str
    user_id: int
    created_at: datetime

    model_config = {"from_Attributes": True}

class CommentListRequestSchema(BaseModel):
    movie_id: int

class CommentListResponseSchema(BaseModel):
    comments: list[CommentListItemSchema]


class CommentReplyCreateRequestSchema(BaseModel):
    user_id: int
    comment_id: int
    text: str

class CommentReplyCreateResponseSchema(BaseModel):
    id: int
    text: str
    movie_id: int
    user_id: int
    parent_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class CommentReplyUpdateRequestSchema(BaseModel):
    comment_id: int
    text: str

class CommentReplyUpdateResponseSchema(BaseModel):
    id: int
    text: str
    movie_id: int
    user_id: int
    parent_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
