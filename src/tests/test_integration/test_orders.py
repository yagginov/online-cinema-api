import os
import random

import pytest
from sqlalchemy import select

from config.dependencies import get_jwt_auth_manager
from config.settings import get_settings
from database import get_db_contextmanager
from database.models.accounts import User, UserGroup, UserGroupEnum
from database.models.movies import MovieModel
from enums.order_enums import OrderStatus
from security import hash_password

URL_PREFIX = "/api/v1"


async def _ensure_user(db_session) -> User:
    res = await db_session.execute(select(UserGroup).where(UserGroup.name == UserGroupEnum.USER))
    group = res.scalars().first()
    if not group:
        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.flush()

    user = User(email=f"buyer{random.randint(1, 999999)}@example.com", group_id=group.id)
    user._hashed_password = hash_password("Password1!")
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth_header(jwt_manager, user_id: int) -> dict[str, str]:
    access = jwt_manager.create_access_token({"user_id": user_id})
    return {"Authorization": f"Bearer {access}"}


@pytest.mark.asyncio
async def test_create_order_and_get_detail(e2e_client, e2e_db_session, seed_database):
    user = await _ensure_user(e2e_db_session)
    os.environ.setdefault("SECRET_KEY_ACCESS", "test_secret")
    os.environ.setdefault("SECRET_KEY_REFRESH", "test_secret")
    jwt_manager = get_jwt_auth_manager(get_settings())  # uses testing settings with fixed secrets
    headers = _auth_header(jwt_manager, user.id)

    res = await e2e_db_session.execute(select(MovieModel.id).limit(3))
    movie_ids = [row[0] for row in res.all()]
    assert movie_ids, "Expected seeded movies for tests"

    resp = await e2e_client.post(f"{URL_PREFIX}/orders/", json={"movie_ids": movie_ids}, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user_id"] == user.id
    assert data["status"] == OrderStatus.PENDING.value
    assert len(data["items"]) == len(movie_ids)

    order_id = data["id"]

    resp = await e2e_client.get(f"{URL_PREFIX}/orders/{order_id}/", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == order_id
    assert detail["user_id"] == user.id


@pytest.mark.asyncio
async def test_list_orders_pagination(e2e_client, e2e_db_session, seed_database):
    user = await _ensure_user(e2e_db_session)
    os.environ.setdefault("SECRET_KEY_ACCESS", "test_secret")
    os.environ.setdefault("SECRET_KEY_REFRESH", "test_secret")
    jwt_manager = get_jwt_auth_manager(get_settings())
    headers = _auth_header(jwt_manager, user.id)

    res = await e2e_db_session.execute(select(MovieModel.id).limit(5))
    movie_ids = [row[0] for row in res.all()]
    for _ in range(3):
        resp = await e2e_client.post(f"{URL_PREFIX}/orders/", json={"movie_ids": movie_ids[:2]}, headers=headers)
        assert resp.status_code == 201

    resp = await e2e_client.get(f"{URL_PREFIX}/orders/?page=1&size=2", headers=headers)
    assert resp.status_code == 200
    lst = resp.json()
    assert lst["page"] == 1
    assert lst["size"] == 2
    assert lst["total_items"] >= 3
    assert len(lst["items"]) == 2


@pytest.mark.asyncio
async def test_cancel_order(e2e_client, e2e_db_session, seed_database):
    user = await _ensure_user(e2e_db_session)
    os.environ.setdefault("SECRET_KEY_ACCESS", "test_secret")
    os.environ.setdefault("SECRET_KEY_REFRESH", "test_secret")
    jwt_manager = get_jwt_auth_manager(get_settings())
    headers = _auth_header(jwt_manager, user.id)

    res = await e2e_db_session.execute(select(MovieModel.id).limit(2))
    movie_ids = [row[0] for row in res.all()]
    resp = await e2e_client.post(f"{URL_PREFIX}/orders/", json={"movie_ids": movie_ids}, headers=headers)
    assert resp.status_code == 201
    order_id = resp.json()["id"]

    del_resp = await e2e_client.delete(f"{URL_PREFIX}/orders/{order_id}/", headers=headers)
    assert del_resp.status_code == 204

    get_resp = await e2e_client.get(f"{URL_PREFIX}/orders/{order_id}/", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == OrderStatus.CANCELED.value
