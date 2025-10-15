import json
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from config.dependencies import get_accounts_email_notificator
from config.dependencies import get_settings as dep_get_settings
from database.models import MovieModel
from database.models.accounts import User, UserGroup, UserGroupEnum
from database.models.orders import OrderModel
from database.models.payments import PaymentModel
from enums.order_enums import OrderStatus
from enums.payment_enums import PaymentStatus
from main import app
from repositories.orders import OrderRepository
from security.token_manager import JWTAuthManager

URL_PREFIX = "/api/v1"


async def _create_user(db_session, email: str | None = None) -> User:
    result = await db_session.execute(select(UserGroup).where(UserGroup.name == UserGroupEnum.USER))
    group = result.scalars().first()
    if not group:
        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.flush()
    if email is None:
        email = f"user_{uuid4().hex[:8]}@example.com"
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


async def _get_or_create_group(db_session, group_name: UserGroupEnum) -> UserGroup:
    result = await db_session.execute(select(UserGroup).where(UserGroup.name == group_name))
    group = result.scalars().first()
    if not group:
        group = UserGroup(name=group_name)
        db_session.add(group)
        await db_session.flush()
    return group


async def _create_admin_user(db_session, email: str) -> User:
    group = await _get_or_create_group(db_session, UserGroupEnum.ADMIN)
    user = User.create(email=email, raw_password="StrongP@ssw0rd!", group_id=group.id)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _override_settings():
    settings = dep_get_settings()
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_123"
    settings.PAYMENT_SUCCESS_URL = "http://success.local/"
    settings.PAYMENT_CANCEL_URL = "http://cancel.local/"
    app.dependency_overrides[dep_get_settings] = lambda: settings
    return settings


def _auth_header(settings, user_id: int) -> dict[str, str]:
    jwt = JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )
    token = jwt.create_access_token({"user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_payment_returns_url_and_persists(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    created_session = {"id": "cs_test_123", "url": "https://stripe.test/checkout/cs_test_123"}

    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: created_session)

    payload = {"order_id": order.id}
    response = await client.post(
        f"{URL_PREFIX}/payments/",
        json=payload,
        headers=_auth_header(settings, user.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["payment_url"] == created_session["url"]
    assert data["order_id"] == order.id
    assert Decimal(str(data["amount"])) == Decimal(str(order.total_amount))
    assert data["status"] == PaymentStatus.PENDING

    payment = (await db_session.execute(PaymentModel.__table__.select())).fetchone()
    assert payment is not None
    assert payment.external_payment_id == created_session["id"]
    assert payment.amount == order.total_amount
    assert payment.status == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_create_payment_requires_stripe_config(client, db_session, seed_database):
    settings = dep_get_settings()
    app.dependency_overrides[dep_get_settings] = lambda: settings

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    response = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_webhook_marks_payment_success_and_order_paid(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    created_session = {"id": "cs_test_456", "url": "https://stripe.test/checkout/cs_test_456"}

    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: created_session)

    create_resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    def fake_construct_event(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": created_session["id"],
                    "metadata": {"payment_id": str(payment_id), "order_id": str(order.id), "user_id": str(user.id)},
                }
            },
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))

    body = json.dumps({"some": "payload"})
    webhook_resp = await client.post(
        f"{URL_PREFIX}/payments/webhook/",
        content=body,
        headers={"stripe-signature": "t=123,v1=abc"},
    )
    assert webhook_resp.status_code == 200

    payment_row = (await db_session.execute(PaymentModel.__table__.select())).fetchone()
    order_row = (await db_session.execute(OrderModel.__table__.select().where(OrderModel.id == order.id))).fetchone()
    assert payment_row.status == PaymentStatus.SUCCESSFUL
    assert order_row.status == OrderStatus.PAID


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400(client):
    resp = await client.post(f"{URL_PREFIX}/payments/webhook/", content=b"{}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_expired_marks_payment_canceled(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    created_session = {"id": "cs_test_expired", "url": "https://stripe.test/checkout/cs_test_expired"}
    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: created_session)

    create_resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert create_resp.status_code == 201

    def fake_construct_event(payload, sig_header, secret):  # noqa: ARG001
        return {"type": "checkout.session.expired", "data": {"object": {"id": created_session["id"]}}}

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))

    resp = await client.post(
        f"{URL_PREFIX}/payments/webhook/",
        content=b"{}",
        headers={"stripe-signature": "t=123,v1=abc"},
    )
    assert resp.status_code == 200

    payment_row = (await db_session.execute(PaymentModel.__table__.select())).fetchone()
    assert payment_row.status == PaymentStatus.CANCELED


@pytest.mark.asyncio
async def test_create_payment_order_already_paid_returns_400(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    created_session = {"id": "cs_test_paid", "url": "https://stripe.test/checkout/cs_test_paid"}
    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: created_session)

    create_resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    def fake_construct_event(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "checkout.session.completed",
            "data": {"object": {"id": created_session["id"], "metadata": {"payment_id": str(payment_id)}}},
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))
    _ = await client.post(
        f"{URL_PREFIX}/payments/webhook/",
        content=b"{}",
        headers={"stripe-signature": "t=123,v1=abc"},
    )

    resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_payment_for_other_user_order_forbidden(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user1 = await _create_user(db_session, email="user1@example.com")
    user2 = await _create_user(db_session, email="user2@example.com")
    order = await _create_order_for_user(db_session, user1.id)

    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: {"id": "cs_test", "url": "u"})

    resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user2.id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stripe_failure_returns_502(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    import stripe

    def raise_err(**kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(stripe.checkout.Session, "create", raise_err)

    resp = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_create_payment_reuses_pending_session(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    import stripe

    first_session = {"id": "cs_reuse_1", "url": "https://stripe.test/checkout/cs_reuse_1"}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: first_session)

    resp1 = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert resp1.status_code == 201
    url1 = resp1.json()["payment_url"]

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(lambda sid: first_session))

    resp2 = await client.post(
        f"{URL_PREFIX}/payments/",
        json={"order_id": order.id},
        headers=_auth_header(settings, user.id),
    )
    assert resp2.status_code == 201
    url2 = resp2.json()["payment_url"]
    assert url2 == url1

    result = await db_session.execute(select(func.count()).select_from(PaymentModel))
    count = result.scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_list_my_payments_filters(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()
    import stripe

    user = await _create_user(db_session)
    order1 = await _create_order_for_user(db_session, user.id)
    order2 = await _create_order_for_user(db_session, user.id)

    s1 = {"id": "cs_list_1", "url": "https://stripe.test/checkout/cs_list_1"}
    s2 = {"id": "cs_list_2", "url": "https://stripe.test/checkout/cs_list_2"}
    sessions = [s1, s2]

    def create_session(**kwargs):  # noqa: ARG001
        return sessions.pop(0)

    monkeypatch.setattr(stripe.checkout.Session, "create", create_session)

    r1 = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": order1.id}, headers=_auth_header(settings, user.id)
    )
    r2 = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": order2.id}, headers=_auth_header(settings, user.id)
    )
    assert r1.status_code == 201 and r2.status_code == 201
    p1_id = r1.json()["id"]

    def make_completed(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "checkout.session.completed",
            "data": {"object": {"id": s1["id"], "metadata": {"payment_id": str(p1_id)}}},
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(make_completed))
    _ = await client.post(f"{URL_PREFIX}/payments/webhook/", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    resp = await client.get(f"{URL_PREFIX}/payments/?status=successful", headers=_auth_header(settings, user.id))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] >= 1
    assert all(item["status"] == PaymentStatus.SUCCESSFUL for item in data["items"])


@pytest.mark.asyncio
async def test_admin_list_payments_requires_admin(client, db_session, seed_database):
    settings = _override_settings()
    user = await _create_user(db_session)
    resp = await client.get(f"{URL_PREFIX}/admin/payments/", headers=_auth_header(settings, user.id))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_payments_filters_by_user(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()
    import stripe

    admin = await _create_admin_user(db_session, email="admin@example.com")
    user1 = await _create_user(db_session, email="u1@example.com")
    user2 = await _create_user(db_session, email="u2@example.com")

    o1 = await _create_order_for_user(db_session, user1.id)
    o2 = await _create_order_for_user(db_session, user2.id)

    s1 = {"id": "cs_admin_1", "url": "https://stripe.test/checkout/cs_admin_1"}
    s2 = {"id": "cs_admin_2", "url": "https://stripe.test/checkout/cs_admin_2"}
    admin_sessions = [s1, s2]

    def create_admin_session(**kwargs):  # noqa: ARG001
        return admin_sessions.pop(0)

    monkeypatch.setattr(stripe.checkout.Session, "create", create_admin_session)

    r1 = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": o1.id}, headers=_auth_header(settings, user1.id)
    )
    r2 = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": o2.id}, headers=_auth_header(settings, user2.id)
    )
    assert r1.status_code == 201 and r2.status_code == 201

    resp = await client.get(
        f"{URL_PREFIX}/admin/payments/?user_id={user1.id}", headers=_auth_header(settings, admin.id)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["user_id"] == user1.id for item in data["items"])


@pytest.mark.asyncio
async def test_webhook_sends_receipt_email(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()
    import stripe

    class FakeSender:
        def __init__(self):
            self.calls: list[dict] = []

        async def send_payment_receipt_email(
            self, email: str, *, payment_id: int, order_id: int, amount: str, created_at: str
        ) -> None:  # noqa: E501
            self.calls.append(
                {
                    "email": email,
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": amount,
                    "created_at": created_at,
                }
            )

    sender = FakeSender()
    app.dependency_overrides[get_accounts_email_notificator] = lambda: sender

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    session = {"id": "cs_email_1", "url": "https://stripe.test/checkout/cs_email_1"}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: session)

    r = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": order.id}, headers=_auth_header(settings, user.id)
    )
    assert r.status_code == 201
    payment_id = r.json()["id"]

    def completed(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session["id"],
                    "payment_intent": "pi_email_1",
                    "metadata": {"payment_id": str(payment_id)},
                }
            },
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(completed))
    _ = await client.post(f"{URL_PREFIX}/payments/webhook/", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    assert len(sender.calls) == 1
    call = sender.calls[0]
    assert call["email"] == user.email
    assert call["payment_id"] == payment_id


@pytest.mark.asyncio
async def test_refund_webhook_marks_payment_refunded(client, db_session, seed_database, monkeypatch):
    settings = _override_settings()
    import stripe

    user = await _create_user(db_session)
    order = await _create_order_for_user(db_session, user.id)

    session = {"id": "cs_refund_1", "url": "https://stripe.test/checkout/cs_refund_1"}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: session)

    r = await client.post(
        f"{URL_PREFIX}/payments/", json={"order_id": order.id}, headers=_auth_header(settings, user.id)
    )
    assert r.status_code == 201
    payment_id = r.json()["id"]

    def completed(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session["id"],
                    "payment_intent": "pi_refund_1",
                    "metadata": {"payment_id": str(payment_id)},
                }
            },
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(completed))
    _ = await client.post(f"{URL_PREFIX}/payments/webhook/", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    def charge_refunded(payload, sig_header, secret):  # noqa: ARG001
        return {
            "type": "charge.refunded",
            "data": {
                "object": {
                    "object": "charge",
                    "id": "ch_123",
                    "payment_intent": "pi_refund_1",
                }
            },
        }

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(charge_refunded))
    _ = await client.post(f"{URL_PREFIX}/payments/webhook/", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    row = (await db_session.execute(PaymentModel.__table__.select())).fetchone()
    assert row.status == PaymentStatus.REFUNDED
