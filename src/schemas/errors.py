from pydantic import BaseModel


class NotFoundErrorResponse(BaseModel):
    detail: str
