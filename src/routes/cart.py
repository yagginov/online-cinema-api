from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.cart import CartModel
from src.database import get_db

from schemas.carts import CartResponseSchema


router = APIRouter()

@router.get(
    "/users/{user_id}/shopping-cart/",
    response_model=CartResponseSchema,
    status_code=200,
    description=(
        "<h3>Get user's shopping cart with list of movies user added to cart."
        "If cart doesn't exist yet it will be created when accessing this "
        "endpoint</h3>"
    ),
)
async def get_cart(user_id: int,
                   db: AsyncSession = Depends(get_db)):
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please register or log in to add movies to access your cart.",
        )
    cart_stmt = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(cart_stmt)
    cart = result.scalars().first()
    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    return CartResponseSchema(
        id=cart.id,
        movies=[item.movie_id for item in cart.items] if cart.items else []
    )
