import pytest
from sqlalchemy import select

from database.models import MovieModel
from database.models.accounts import User, UserGroup, UserGroupEnum
from database.models.orders import OrderModel
from repositories.orders import OrderRepository
from fastapi import HTTPException


async def _get_or_create_user_group(db_session) -> UserGroup:
    result = await db_session.execute(select(UserGroup).where(UserGroup.name == UserGroupEnum.USER))
    group = result.scalars().first()
    if not group:
        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.flush()
    return group


async def _create_user(db_session, email: str) -> User:
    group = await _get_or_create_user_group(db_session)
    user = User.create(email=email, raw_password="StrongP@ssw0rd!", group_id=group.id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_order_unique_movies_and_total(db_session, seed_database):
    user = await _create_user(db_session, email="order_repo1@example.com")
    movies = (await db_session.execute(MovieModel.__table__.select().limit(2))).fetchall()
    m1, m2 = movies[0], movies[1]

    repo = OrderRepository(OrderModel, db_session)
    order = await repo.create_order(user_id=user.id, movie_ids=[m1.id, m1.id, m2.id])

    assert order.user_id == user.id
    assert len(order.items) == 2
    expected_total = m1.price + m2.price
    assert order.total_amount == expected_total


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_order_missing_movie_raises(db_session, seed_database):
    user = await _create_user(db_session, email="order_repo2@example.com")
    max_id = (await db_session.execute(select(MovieModel.id).order_by(MovieModel.id.desc()).limit(1))).scalar()
    non_exist = (max_id or 0) + 9999

    repo = OrderRepository(OrderModel, db_session)
    with pytest.raises(HTTPException) as exc:
        await repo.create_order(user_id=user.id, movie_ids=[non_exist])
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_object_and_total_and_ordering(db_session, seed_database):
    user = await _create_user(db_session, email="order_repo3@example.com")
    movies = (await db_session.execute(MovieModel.__table__.select().limit(3))).fetchall()

    repo = OrderRepository(OrderModel, db_session)
    o1 = await repo.create_order(user_id=user.id, movie_ids=[movies[0].id])
    o2 = await repo.create_order(user_id=user.id, movie_ids=[movies[1].id, movies[2].id])

    got = await repo.get_object(id=o1.id)
    assert got is not None
    assert got.id == o1.id
    assert len(got.items) == 1

    items = await repo.get_objects(filters={"user_id": user.id}, ordering=["-created_at"], limit=10)
    assert len(items) >= 2
    assert items[0].created_at >= items[1].created_at

    total = await repo.get_total(filters={"user_id": user.id})
    assert total >= 2

