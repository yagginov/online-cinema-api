import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AnyUrl
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_jwt_auth_manager
from database import get_db
from enums.order_enums import OrderStatus
from repositories.orders import OrderRepository, get_order_repository
from schemas.orders import (
    OrderCreateRequestSchema,
    OrderPaginatedResponseSchema,
    OrderResponseSchema,
)
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


def get_user_id(token: str, jwt_manager: JWTAuthManagerInterface) -> int:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if not isinstance(user_id, int):
            raise ValueError("user_id missing or invalid")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


@router.post(
    "/orders/",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponseSchema,
    summary="Create order",
    description="""
    Create a new order for selected movies.
    
    **Process:**
    1. Validates JWT token
    2. Checks if all movies exist
    3. Calculates total amount
    4. Creates order with status PENDING
    5. Locks movie prices at order creation time
    
    **Authentication:** Required (Bearer token)
    """,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing authentication token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "One or more movies not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with id=999 not found"}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "examples": {
                        "empty_list": {
                            "summary": "Empty movie list",
                            "value": {"detail": "Movie list cannot be empty"}
                        },
                        "duplicates": {
                            "summary": "Duplicate movies",
                            "value": {"detail": "Duplicate movie IDs in the order"}
                        }
                    }
                }
            }
        }
    }
)
async def create_order(
    data: OrderCreateRequestSchema,
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> OrderResponseSchema:
    user_id = get_user_id(token, jwt_manager)
    order = await order_repo.create_order(user_id=user_id, movie_ids=data.movie_ids)
    return OrderResponseSchema.model_validate(
        {
            "id": order.id,
            "user_id": order.user_id,
            "status": order.status.value,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
            "items": [{"movie_id": it.movie_id, "price_at_order": it.price_at_order} for it in order.items],
        }
    )


@router.get(
    "/orders/",
    response_model=OrderPaginatedResponseSchema,
    summary="List my orders",
    description="""
    Returns paginated list of current user's orders.
    
    **Features:**
    - Orders sorted by creation date (newest first)
    - Pagination support
    - Only shows orders belonging to authenticated user
    
    **Authentication:** Required (Bearer token)
    """,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            }
        }
    },
)
async def list_orders(
    request: Request,
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> OrderPaginatedResponseSchema:
    user_id = get_user_id(token, jwt_manager)
    orders = await order_repo.get_objects(
        filters={"user_id": user_id},
        offset=(page - 1) * size,
        limit=size,
        ordering=["-created_at"],
    )
    total = await order_repo.get_total(filters={"user_id": user_id})
    total_pages = max(1, math.ceil(total / size)) if total else 1

    next_page = AnyUrl(str(request.url.replace_query_params(page=page + 1, size=size))) if page < total_pages else None
    prev_page = AnyUrl(str(request.url.replace_query_params(page=page - 1, size=size))) if page > 1 else None

    items = [
        OrderResponseSchema.model_validate(
            {
                "id": o.id,
                "user_id": o.user_id,
                "status": o.status.value,
                "total_amount": o.total_amount,
                "created_at": o.created_at,
                "items": [{"movie_id": it.movie_id, "price_at_order": it.price_at_order} for it in o.items],
            }
        )
        for o in orders
    ]

    return OrderPaginatedResponseSchema(
        items=items,
        page=page,
        size=size,
        total_items=total,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )


@router.get(
    "/orders/{order_id}/",
    response_model=OrderResponseSchema,
    summary="Get order detail",
    description="""
    Returns detailed information about a specific order.
    
    **Security:**
    - Users can only view their own orders
    - Attempting to access another user's order returns 403 Forbidden
    
    **Authentication:** Required (Bearer token)
    """,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            }
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Access to another user's order is forbidden",
            "content": {
                "application/json": {
                    "example": {"detail": "Forbidden"}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Order not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Order with id=42 not found"}
                }
            }
        },
    },
)
async def get_order(
    order_id: int,
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> OrderResponseSchema:
    user_id = get_user_id(token, jwt_manager)
    order = await order_repo.get_object_or_404(id=order_id)
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return OrderResponseSchema.model_validate(
        {
            "id": order.id,
            "user_id": order.user_id,
            "status": order.status.value,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
            "items": [{"movie_id": it.movie_id, "price_at_order": it.price_at_order} for it in order.items],
        }
    )


@router.delete(
    "/orders/{order_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel order",
    description="""
    Cancel an existing order.
    
    **Rules:**
    - Only orders with status PENDING can be canceled
    - Completed or already canceled orders cannot be canceled
    - Users can only cancel their own orders
    
    **Authentication:** Required (Bearer token)
    """,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Order cannot be canceled",
            "content": {
                "application/json": {
                    "example": {"detail": "Only pending orders can be canceled"}
                }
            }
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            }
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Cannot cancel another user's order",
            "content": {
                "application/json": {
                    "example": {"detail": "Forbidden"}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Order not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Order with id=42 not found"}
                }
            }
        },
    },
)
async def cancel_order(
    order_id: int,
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
) -> None:
    user_id = get_user_id(token, jwt_manager)
    order = await order_repo.get_object_or_404(id=order_id)
    if order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending orders can be canceled")
    order.status = OrderStatus.CANCELED
    db.add(order)
    await db.commit()
    return None
