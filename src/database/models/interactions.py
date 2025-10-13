import enum
from sqlalchemy import Enum, Column, Integer
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates
)

from src.database import Base


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroup(Base):
    __tablename__ = "user_groups table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[UserGroupEnum] = mapped_column(Enum(UserGroupEnum), nullable=False, unique=True)

    def __repr__(self):
        return f"<UserGroupModel(id={self.id}, name={self.name})>"

