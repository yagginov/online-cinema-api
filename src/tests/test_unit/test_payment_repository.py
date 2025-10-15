import pytest
from sqlalchemy import select

from database.models import MovieModel
from database.models.accounts import User, UserGroup, UserGroupEnum
from database.models.orders import OrderModel
from database.models.payments import PaymentItemModel, PaymentModel
from enums.payment_enums import PaymentStatus
from repositories.orders import OrderRepository
from repositories.payments import PaymentRepository


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


async def _create_order_for_user(db_session, user_id: int) -> OrderModel:
    movies = (await db_session.execute(MovieModel.__table__.select().limit(2))).fetchall()
    movie_ids = [row.id for row in movies]
    repo = OrderRepository(OrderModel, db_session)
    return await repo.create_order(user_id=user_id, movie_ids=movie_ids)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_external_payment_id_returns_payment_with_items(db_session, seed_database):
    user = await _create_user(db_session, email="repo_user1@example.com")
    order = await _create_order_for_user(db_session, user.id)

    payment = PaymentModel(
        user_id=user.id,
        order_id=order.id,
        status=PaymentStatus.PENDING,
        amount=order.total_amount,
        external_payment_id="cs_repo_123",
    )
    db_session.add(payment)
    await db_session.flush()

    for item in order.items:
        db_session.add(
            PaymentItemModel(
                payment_id=payment.id, order_item_id=item.id, price_at_payment=item.price_at_order
            )
        )
    await db_session.commit()

    repo = PaymentRepository(PaymentModel, db_session)
    found = await repo.get_by_external_payment_id("cs_repo_123")
    assert found is not None
    assert found.id == payment.id
    assert len(found.items) == len(order.items)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_objects_filters_and_ordering(db_session, seed_database):
    user = await _create_user(db_session, email="repo_user2@example.com")
    order = await _create_order_for_user(db_session, user.id)

    p1 = PaymentModel(
        user_id=user.id,
        order_id=order.id,
        status=PaymentStatus.PENDING,
        amount=order.total_amount,
        external_payment_id="cs_repo_a",
    )
    p2 = PaymentModel(
        user_id=user.id,
        order_id=order.id,
        status=PaymentStatus.PENDING,
        amount=order.total_amount,
        external_payment_id="cs_repo_b",
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    repo = PaymentRepository(PaymentModel, db_session)
    items = await repo.get_objects(filters={"user_id": user.id}, ordering=["-id"])
    assert len(items) >= 2
    assert items[0].id > items[1].id


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_object_returns_none_for_missing(db_session, seed_database):
    repo = PaymentRepository(PaymentModel, db_session)
    obj = await repo.get_object(id=-1)
    assert obj is None

