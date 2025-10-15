from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import User
from database.models import MovieModel, OrderItemModel, OrderModel
from database.models.cart import CartModel, CartItemModel
from database import get_db
from enums.order_enums import OrderStatus

from schemas.carts import (
    CartResponseSchema,
    CartDeleteResponseSchema,
    CartListItemSchema,
)

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
async def get_cart(user_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please register or log in to add movies to access your cart.",
        )
    cart_stmt = select(CartModel).options(selectinload(CartModel.items)).where(CartModel.user_id == user_id)

    result = await db.execute(cart_stmt)
    cart = result.scalars().first()

    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
        items_list = []
    else:
        movie_ids = [item.movie_id for item in cart.items]
        movies_stmt = select(MovieModel).where(MovieModel.id.in_(movie_ids)).options(selectinload(MovieModel.genres))
        result = await db.execute(movies_stmt)
        movies = result.scalars().all()

        items_list = []
        for movie in movies:
            items_list.append(
                CartListItemSchema.model_validate(
                    {
                        "id": movie.id,
                        "name": movie.name,
                        "price": movie.price,
                        "genres": ", ".join(g.name for g in movie.genres),
                        "year": movie.year,
                    }
                )
            )

    return CartResponseSchema(id=cart.id, movies=items_list)


@router.post(
    "/users/{user_id}/shopping-cart/add/{movie_id}/",
    response_model=CartResponseSchema,
    status_code=200,
    description="<h3>Allows user adding movies to shopping cart."
    "If shopping cart doesn't exist yet, creates it "
    "automatically</h3>",
)
async def add_movie_to_cart(
    movie_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):

    stmt = select(User).where(User.id == user_id)

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
        await db.flush()

    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail=f"Movie with id {movie_id} doesn't exist")

    item_stmt = select(CartItemModel).where(CartItemModel.cart_id == cart.id, CartItemModel.movie_id == movie_id)
    result = await db.execute(item_stmt)
    existing_item = result.scalars().first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This movie is already " "in your cart.")
    cart_item = CartItemModel(
        cart_id=cart.id,
        movie_id=movie_id,
    )
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart)

    purchased_movie_stmt = (
        select(OrderItemModel)
        .join(OrderModel)
        .where(
            OrderModel.user_id == user_id,
            OrderModel.status == OrderStatus.PAID,
            OrderItemModel.movie_id == movie_id,
        )
    )
    result = await db.execute(purchased_movie_stmt)
    purchased_movie = result.scalars().all()

    if purchased_movie:
        raise HTTPException(status_code=400, detail="You have already purchased this movie.")

    item_stmt = select(CartItemModel.movie_id).where(CartItemModel.cart_id == cart.id)
    result = await db.execute(item_stmt)
    movie_ids = result.scalars().all()

    movies_stmt = select(MovieModel).where(MovieModel.id.in_(movie_ids)).options(selectinload(MovieModel.genres))
    result = await db.execute(movies_stmt)
    movies = result.scalars().all()

    items_list = []
    for movie in movies:
        items_list.append(
            CartListItemSchema(
                id=movie.id,
                name=movie.name,
                price=movie.price,
                genres=", ".join(g.name for g in movie.genres),
                year=movie.year,
            )
        )

    return CartResponseSchema(id=cart.id, movies=items_list)


@router.delete(
    "/users/{user_id}/shopping-cart/remove/{movie_id}/",
    response_model=CartResponseSchema,
    status_code=200,
    description="<h3>Allows user removing movies from shopping cart " "by " "deleting CartItem object.</h3>",
)
async def remove_movie_from_cart(user_id: int, movie_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.id == user_id)

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
        raise HTTPException(status_code=400, detail="Cart not found")

    item_stmt = select(CartItemModel).where(CartItemModel.cart_id == cart.id, CartItemModel.movie_id == movie_id)

    result = await db.execute(item_stmt)
    existing_item = result.scalars().first()
    if not existing_item:
        raise HTTPException(status_code=400, detail="This movie wasn't in your cart")

    await db.delete(existing_item)
    await db.commit()
    await db.refresh(cart)

    item_stmt = select(CartItemModel.movie_id).where(CartItemModel.cart_id == cart.id)
    result = await db.execute(item_stmt)
    movie_ids = result.scalars().all()

    movies_stmt = select(MovieModel).where(MovieModel.id.in_(movie_ids)).options(selectinload(MovieModel.genres))
    result = await db.execute(movies_stmt)
    movies = result.scalars().all()

    items_list = []
    for movie in movies:
        items_list.append(
            CartListItemSchema(
                id=movie.id,
                name=movie.name,
                price=movie.price,
                genres=", ".join(g.name for g in movie.genres),
                year=movie.year,
            )
        )

    return CartResponseSchema(id=cart.id, movies=items_list)


@router.delete(
    "/users/{user_id}/shopping-cart/delete/",
    response_model=CartDeleteResponseSchema,
    status_code=200,
    description="<h3>Allows user to clear their cart</h3>",
)
async def clear_shopping_cart(user_id: int, db: AsyncSession = Depends(get_db)):

    stmt = select(User).where(User.id == user_id)

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
        raise HTTPException(status_code=400, detail="Cart not found.")

    movies_stmt = select(CartItemModel).where(CartItemModel.cart_id == cart.id)
    result = await db.execute(movies_stmt)
    cart_items = result.scalars().all()

    for cart_item in cart_items:
        await db.delete(cart_item)

    await db.commit()
    await db.refresh(cart)

    return CartDeleteResponseSchema(user_id=user_id)
