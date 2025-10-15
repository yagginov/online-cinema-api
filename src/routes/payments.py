from __future__ import annotations

from decimal import Decimal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.dependencies import get_jwt_auth_manager, get_settings
from config.settings import BaseAppSettings
from database import get_db
from database.models.orders import OrderItemModel, OrderModel
from database.models.payments import PaymentItemModel, PaymentModel
from enums.order_enums import OrderStatus
from enums.payment_enums import PaymentStatus
from schemas.payments import PaymentCreateRequestSchema, PaymentCreateResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface


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


@router.post(
    "/payments/",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentCreateResponseSchema,
    summary="Create payment and return checkout URL",
)
async def create_payment(
    data: PaymentCreateRequestSchema,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
) -> PaymentCreateResponseSchema:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    user_id = _get_user_id(token, jwt_manager)

    stmt = (
        select(OrderModel)
        .where(OrderModel.id == data.order_id)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
    )
    result = await db.execute(stmt)
    order: OrderModel | None = result.scalars().first()

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending orders can be paid")
    if order.total_amount is None or Decimal(str(order.total_amount)) <= Decimal("0"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order has invalid total amount")

    existing_stmt = select(PaymentModel).where(
        PaymentModel.order_id == order.id, PaymentModel.status == PaymentStatus.SUCCESSFUL
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    payment = PaymentModel(
        user_id=user_id,
        order_id=order.id,
        status=PaymentStatus.PENDING,
        amount=order.total_amount,
    )
    db.add(payment)
    await db.flush()

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
            success_url=getattr(settings, "PAYMENT_SUCCESS_URL", "http://localhost:8000/")
            or "http://localhost:8000/",
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
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
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

    async def _get_payment_by_session() -> PaymentModel | None:
        metadata = data_object.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        if payment_id and str(payment_id).isdigit():
            stmt = select(PaymentModel).where(PaymentModel.id == int(payment_id))
            res = await db.execute(stmt)
            return res.scalars().first()
        session_id = data_object.get("id")
        if session_id:
            stmt = select(PaymentModel).where(PaymentModel.external_payment_id == session_id)
            res = await db.execute(stmt)
            return res.scalars().first()
        return None

    payment: PaymentModel | None = None

    if event_type == "checkout.session.completed":
        payment = await _get_payment_by_session()
        if payment:
            order = await db.get(OrderModel, payment.order_id)
            payment.status = PaymentStatus.SUCCESSFUL
            if order and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.PAID
                db.add(order)
            db.add(payment)
            await db.commit()
        return {"status": "ok"}

    if event_type == "checkout.session.expired":
        payment = await _get_payment_by_session()
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
