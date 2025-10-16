from decimal import Decimal
from typing import Annotated, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models import MovieModel
from database.models.orders import OrderItemModel, OrderModel
from repositories.generic import AsyncRepository


class OrderRepository(AsyncRepository[OrderModel]):
    async def create_order(self, *args, user_id: int, movie_ids: list[int]) -> OrderModel:
        unique_ids = list(dict.fromkeys(movie_ids))
        if not unique_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No movies provided")

        stmt_movies = select(MovieModel).where(MovieModel.id.in_(unique_ids))
        result = await self.session.execute(stmt_movies)
        movies = result.scalars().all()
        if len(movies) != len(unique_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more movies not found")

        order = OrderModel(user_id=user_id)
        self.session.add(order)
        await self.session.flush()

        total = Decimal("0")
        for movie in movies:
            price = movie.price
            order_item = OrderItemModel(order_id=order.id, movie_id=movie.id, price_at_order=price)
            self.session.add(order_item)
            total += Decimal(str(price))

        order.total_amount = total
        await self.session.commit()
        await self.session.refresh(order)
        return await self.get_object_or_404(id=order.id)

    @staticmethod
    def _with_items(stmt: Select) -> Select:
        return stmt.options(joinedload(OrderModel.items).joinedload(OrderItemModel.movie))

    async def get_object(self, **filters) -> OrderModel | None:
        stmt = self._with_items(select(self.model).filter_by(**filters))
        result = await self.session.execute(stmt)
        return result.unique().scalars().first()

    async def get_objects(
        self,
        *args,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 100,
        ordering: list[str] | None = None,
    ) -> Sequence[OrderModel]:
        stmt = self._with_items(select(self.model))
        if filters:
            stmt = stmt.filter_by(**filters)
        stmt = self._apply_ordering(stmt, ordering)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.unique().scalars().all()


async def get_order_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderRepository:
    return OrderRepository(OrderModel, db)
