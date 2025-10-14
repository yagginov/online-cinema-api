from pydantic import BaseModel, ConfigDict


class CertificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
