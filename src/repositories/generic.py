from typing import Generic, Optional, Sequence, Type, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, asc, delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class AsyncRepository(Generic[T]):
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def create_object(self, data: dict | BaseModel, *, flush_only: bool = False) -> T:
        if isinstance(data, BaseModel):
            data = data.model_dump()
        obj = self.model(**data)
        self.session.add(obj)
        if flush_only:
            await self.session.flush()
        else:
            await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_object(self, **filters) -> Optional[T]:
        stmt = select(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_object_or_404(self, **filters) -> T:
        obj = await self.get_object(**filters)
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__.replace("Model", "")} not found for filters={filters}",
            )
        return obj

    def _apply_ordering(
        self,
        stmt: Select,
        ordering: list[str] | None = None,
    ) -> Select:
        if ordering:
            order_by_clauses = []
            for field_name in ordering:
                direction = asc
                if field_name[0] == "-":
                    direction = desc
                    field_name = field_name[1:]
                else:
                    direction = asc
                column = getattr(self.model, field_name, None)
                if not column:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{self.model.__name__.replace("Model", "")}s does not support ordering by this column: {field_name}",
                    )
                order_by_clauses.append(direction(column))
            stmt = stmt.order_by(*order_by_clauses)
        return stmt

    async def get_objects(
        self,
        *,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 100,
        ordering: list[str] | None = None,
    ) -> Sequence[T]:
        stmt = select(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = self._apply_ordering(stmt, ordering)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_objects_or_404(
        self,
        *,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 100,
        ordering: list[str] | None = None,
    ) -> Sequence[T]:
        objects = await self.get_objects(
            filters=filters,
            offset=offset,
            limit=limit,
            ordering=ordering,
        )
        if not objects:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__.replace("Model", "")}s not found.",
            )
        return objects

    async def get_total(self, filters: Optional[dict] = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update_object(self, data: dict | BaseModel, **filters) -> Optional[T]:
        if isinstance(data, BaseModel):
            data = data.model_dump()
        stmt = update(self.model).filter_by(**filters).values(**data).returning(self.model)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalars().first()

    async def delete_object(self, **filters) -> bool:
        stmt = delete(self.model).filter_by(**filters)
        await self.session.execute(stmt)
        try:
            await self.session.commit()
        except IntegrityError:
            return False
        return True

    async def is_exist(self, **filters) -> bool:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return bool(result.scalar())

    async def get_or_create(
        self,
        defaults: dict | BaseModel | None = None,
        *,
        flush_only: bool = False,
        **filters,
    ) -> tuple[T, bool]:
        obj = await self.get_object(**filters)
        if obj:
            return obj, False

        data = {**filters}
        if defaults:
            if isinstance(defaults, BaseModel):
                defaults = defaults.model_dump()
            data.update(defaults)

        new_obj = self.model(**data)
        self.session.add(new_obj)

        if flush_only:
            await self.session.flush()
        else:
            await self.session.commit()

        await self.session.refresh(new_obj)
        return new_obj, True
