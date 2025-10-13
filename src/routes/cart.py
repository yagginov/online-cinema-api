from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.cart import CartModel, CartItemModel
from src.database import get_db

from schemas.carts import CartResponseSchema, CartUpdateResponseSchema

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

@router.post(
    "/users/{user_id}/shopping-cart/add/{movie_id}",
    response_model=CartUpdateResponseSchema,
    status_code=200,
    description="<h3>Allows user adding movies to shopping cart."
                "If shopping cart doesn't exist yet, creates it "
                "automatically</h3>",
    )
async def cart_update(user_id: int,
                      movie_id: int,
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

    item_stmt = select(CartItemModel).where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id == movie_id)
    result = await db.execute(item_stmt)
    existing_item = result.scalars().first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This movie is already "
                                                    "in your cart.")
    cart_item = CartItemModel(
        cart_id=cart.id,
        movie_id=movie_id,
    )
    db.add(cart_item)
    await db.commit()
    await db.refresh()

    return CartUpdateResponseSchema(
        id=cart.id,
        movies=[item.movie_id for item in cart.items] if cart.items else []
    )
