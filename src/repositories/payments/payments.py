from typing import Annotated, Sequence

from fastapi import Depends
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models.payments import PaymentModel
from repositories.generic import AsyncRepository


class PaymentRepository(AsyncRepository[PaymentModel]):
    @staticmethod
    def _with_items(stmt: Select) -> Select:
        return stmt.options(joinedload(PaymentModel.items))

    async def get_object(self, **filters) -> PaymentModel | None:
        stmt = self._with_items(select(self.model).filter_by(**filters))
        result = await self.session.execute(stmt)
        return result.unique().scalars().first()

    async def get_objects(
        self,
        *,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 100,
        ordering: list[str] | None = None,
    ) -> Sequence[PaymentModel]:
        stmt = self._with_items(select(self.model))
        if filters:
            stmt = stmt.filter_by(**filters)
        stmt = self._apply_ordering(stmt, ordering)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.unique().scalars().all()

    async def get_by_external_payment_id(self, external_payment_id: str) -> PaymentModel | None:
        stmt = self._with_items(select(self.model).where(self.model.external_payment_id == external_payment_id))
        result = await self.session.execute(stmt)
        return result.unique().scalars().first()


async def get_payment_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentRepository:
    return PaymentRepository(PaymentModel, db)

