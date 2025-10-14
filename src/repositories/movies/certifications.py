from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from database.models import CertificationModel
from repositories.generic import AsyncRepository


class CertificationRepository(AsyncRepository[CertificationModel]):
    pass


async def get_certification_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return CertificationRepository(CertificationModel, db)
