from __future__ import annotations

from typing import Annotated
from decimal import Decimal
import math

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AnyUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_jwt_auth_manager, get_settings
from config.dependencies import get_accounts_email_notificator
from config.settings import BaseAppSettings
from database import get_db
from database.models.orders import OrderItemModel, OrderModel
from database.models.payments import PaymentItemModel, PaymentModel
from database.models.accounts import User, UserGroup, UserGroupEnum
from enums.order_enums import OrderStatus
from enums.payment_enums import PaymentStatus
from repositories.orders import OrderRepository, get_order_repository
from repositories.payments import PaymentRepository, get_payment_repository
from schemas.payments import (
    PaymentCreateRequestSchema,
    PaymentCreateResponseSchema,
    PaymentPaginatedResponseSchema,
    PaymentResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from filters.payment_filters import PaymentFilterParams
from notifications.interfaces import EmailSenderInterface

router = APIRouter()


def _get_user_id(token: str, jwt_manager: JWTAuthManagerInterface) -> int:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if not isinstance(user_id, int):
            raise ValueError("user_id missing or invalid")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


async def _get_payment_by_session_data(
    data_object: dict, payment_repo: PaymentRepository
) -> PaymentModel | None:
    metadata = data_object.get("metadata") or {}
    payment_id = metadata.get("payment_id")
    if payment_id and str(payment_id).isdigit():
        return await payment_repo.get_object(id=int(payment_id))
    session_id = data_object.get("id")
    if session_id:
        return await payment_repo.get_by_external_payment_id(session_id)
    return None


@router.post(
    "/payments/",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentCreateResponseSchema,
    summary="Create payment and return checkout URL",
)
async def create_payment(
    data: PaymentCreateRequestSchema,
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
) -> PaymentCreateResponseSchema:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    user_id = _get_user_id(token, jwt_manager)

    order: OrderModel = await order_repo.get_object_or_404(id=data.order_id)
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending orders can be paid")
    if order.total_amount is None or Decimal(str(order.total_amount)) <= Decimal("0"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order has invalid total amount")

    if await payment_repo.get_object(order_id=order.id, status=PaymentStatus.SUCCESSFUL):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    existing_pending: PaymentModel | None = await payment_repo.get_object(
        order_id=order.id, status=PaymentStatus.PENDING
    )
    if existing_pending and existing_pending.external_payment_id:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(existing_pending.external_payment_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Stripe error: {e}") from e
        return PaymentCreateResponseSchema.model_validate(
            {
                "id": existing_pending.id,
                "order_id": existing_pending.order_id,
                "status": existing_pending.status,
                "amount": existing_pending.amount,
                "created_at": existing_pending.created_at,
                "payment_url": session.get("url"),
            }
        )

    payment = await payment_repo.create_object(
        {
            "user_id": user_id,
            "order_id": order.id,
            "status": PaymentStatus.PENDING,
            "amount": order.total_amount,
        },
        flush_only=True,
    )

    for item in order.items:
        db.add(
            PaymentItemModel(
                payment_id=payment.id,
                order_item_id=item.id,
                price_at_payment=item.price_at_order,
            )
        )

    await db.flush()

    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount_cents = int(Decimal(str(order.total_amount)) * 100)

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Order #{order.id}"},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=getattr(settings, "PAYMENT_SUCCESS_URL", "http://localhost:8000/") or "http://localhost:8000/",
            cancel_url=getattr(settings, "PAYMENT_CANCEL_URL", "http://localhost:8000/") or "http://localhost:8000/",
            client_reference_id=str(user_id),
            metadata={
                "payment_id": str(payment.id),
                "order_id": str(order.id),
                "user_id": str(user_id),
            },
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}") from e

    payment.external_payment_id = checkout_session.get("id")
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentCreateResponseSchema.model_validate(
        {
            "id": payment.id,
            "order_id": payment.order_id,
            "status": payment.status,
            "amount": payment.amount,
            "created_at": payment.created_at,
            "payment_url": checkout_session.get("url"),
        }
    )


@router.post(
    "/payments/webhook/",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
)
async def stripe_webhook(
    request: Request,
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload.decode(), sig_header=sig_header, secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {e}") from e

    event_type: str = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})

    payment: PaymentModel | None = None

    if event_type == "checkout.session.completed":
        payment = await _get_payment_by_session_data(data_object, payment_repo)
        if payment:
            order = await db.get(OrderModel, payment.order_id)
            payment.status = PaymentStatus.SUCCESSFUL
            if order and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.PAID
                db.add(order)
            db.add(payment)
            await db.commit()
            try:
                user = await db.get(User, payment.user_id)
                if user and user.email:
                    await email_sender.send_payment_receipt_email(
                        email=user.email,
                        payment_id=payment.id,
                        order_id=payment.order_id,
                        amount=str(payment.amount),
                        created_at=payment.created_at.isoformat(),
                    )
            except Exception:
                pass
        return {"status": "ok"}

    if event_type == "checkout.session.expired":
        payment = await _get_payment_by_session_data(data_object, payment_repo)
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CANCELED
            db.add(payment)
            await db.commit()
        return {"status": "ok"}

    return {"status": "ignored", "event": event_type}


@router.get("/payments/success", summary="Payment success redirect handler")
async def payment_success(session_id: str | None = None):
    return {"status": "success", "session_id": session_id}


@router.get("/payments/cancel", summary="Payment cancel redirect handler")
async def payment_cancel():
    return {"status": "canceled"}


@router.get(
    "/payments/",
    response_model=PaymentPaginatedResponseSchema,
    summary="List my payments",
)
async def list_my_payments(
    request: Request,
    params: Annotated[PaymentFilterParams, Depends()],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> PaymentPaginatedResponseSchema:
    user_id = _get_user_id(token, jwt_manager)
    items, total = await payment_repo.list_payments(params, user_id=user_id)
    total_pages = max(1, math.ceil(total / params.per_page)) if total else 1
    next_page = (
        AnyUrl(str(request.url.replace_query_params(page=params.page + 1)))
        if params.page < total_pages
        else None
    )
    prev_page = AnyUrl(str(request.url.replace_query_params(page=params.page - 1))) if params.page > 1 else None
    return PaymentPaginatedResponseSchema(
        items=[
            PaymentResponseSchema.model_validate(
                {
                    "id": p.id,
                    "order_id": p.order_id,
                    "user_id": p.user_id,
                    "status": p.status,
                    "amount": p.amount,
                    "created_at": p.created_at,
                }
            )
            for p in items
        ],
        page=params.page,
        size=params.per_page,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )


@router.get(
    "/admin/payments/",
    response_model=PaymentPaginatedResponseSchema,
    summary="Admin list payments",
)
async def admin_list_payments(
    request: Request,
    params: Annotated[PaymentFilterParams, Depends()],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
) -> PaymentPaginatedResponseSchema:
    user_id = _get_user_id(token, jwt_manager)
    role_stmt = (
        select(UserGroup.name)
        .join(User, User.group_id == UserGroup.id)
        .where(User.id == user_id)
    )
    role_res = await db.execute(role_stmt)
    role = role_res.scalar_one_or_none()
    if role not in (UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    items, total = await payment_repo.list_payments(params)
    total_pages = max(1, math.ceil(total / params.per_page)) if total else 1
    next_page = (
        AnyUrl(str(request.url.replace_query_params(page=params.page + 1)))
        if params.page < total_pages
        else None
    )
    prev_page = AnyUrl(str(request.url.replace_query_params(page=params.page - 1))) if params.page > 1 else None
    return PaymentPaginatedResponseSchema(
        items=[
            PaymentResponseSchema.model_validate(
                {
                    "id": p.id,
                    "order_id": p.order_id,
                    "user_id": p.user_id,
                    "status": p.status,
                    "amount": p.amount,
                    "created_at": p.created_at,
                }
            )
            for p in items
        ],
        page=params.page,
        size=params.per_page,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )
