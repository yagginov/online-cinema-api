from sqlalchemy import Select, func, select
from sqlalchemy.orm import joinedload

from database.models.payments import PaymentModel
from filters.payment_filters import PaymentFilterParams


class PaymentFilterService:
    @staticmethod
    def _apply_filters(stmt: Select, params: PaymentFilterParams) -> Select:
        if params.status:
            stmt = stmt.where(PaymentModel.status == params.status)
        if params.date_from:
            stmt = stmt.where(PaymentModel.created_at >= params.date_from)
        if params.date_to:
            stmt = stmt.where(PaymentModel.created_at <= params.date_to)
        return stmt

    @staticmethod
    def _apply_ordering(stmt: Select, params: PaymentFilterParams) -> Select:
        ordering = params.get_ordering()
        for field_name in ordering:
            desc = field_name.startswith("-")
            name = field_name[1:] if desc else field_name
            column = getattr(PaymentModel, name)
            stmt = stmt.order_by(column.desc() if desc else column.asc())
        return stmt

    @classmethod
    async def list_payments(
        cls,
        session,
        params: PaymentFilterParams,
        *,
        user_id: int | None = None,
    ) -> tuple[list[PaymentModel], int]:
        stmt = select(PaymentModel).options(joinedload(PaymentModel.items))
        count_stmt = select(func.count()).select_from(PaymentModel)

        if user_id:
            stmt = stmt.where(PaymentModel.user_id == user_id)
            count_stmt = count_stmt.where(PaymentModel.user_id == user_id)
        if params.user_id:
            stmt = stmt.where(PaymentModel.user_id == params.user_id)
            count_stmt = count_stmt.where(PaymentModel.user_id == params.user_id)

        stmt = cls._apply_filters(stmt, params)
        count_stmt = cls._apply_filters(count_stmt, params)
        stmt = cls._apply_ordering(stmt, params)
        stmt = stmt.offset(params.get_offset()).limit(params.per_page)

        result = await session.execute(stmt)
        items = result.unique().scalars().all()

        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        return items, int(total)
