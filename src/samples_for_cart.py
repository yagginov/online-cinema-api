import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from database.models.accounts import User, UserGroup, UserGroupEnum
from database.models.movies import MovieModel, GenreModel, StarModel, DirectorModel, CertificationModel
from database.models.cart import CartModel, CartItemModel

DATABASE_URL = "postgresql+asyncpg://admin:secret@127.0.0.1:5432/cinema"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_sample_data():
    async with async_session_maker() as session:
        existing_groups = await session.execute(select(UserGroup.name))
        existing = {g[0] for g in existing_groups}

        for name in UserGroupEnum:
            if name not in existing:
                session.add(UserGroup(name=name))
        await session.commit()

        groups_result = await session.execute(select(UserGroup).order_by(UserGroup.id))
        groups = groups_result.scalars().all()

        user1 = User(
            email="stinkycat@example.com",
            _hashed_password="hashed_aaa111",
            is_active=True,
            group_id=groups[0].id,
        )
        user2 = User(
            email="smellycat@example.com",
            _hashed_password="hashed_bbb222",
            is_active=True,
            group_id=groups[1].id,
        )
        session.add_all([user1, user2])
        await session.commit()

        cert_pg13 = CertificationModel(name="allowed for cats")
        session.add(cert_pg13)
        await session.commit()

        genre_meow = GenreModel(name="Meowling")
        genre_bark = GenreModel(name="Barking")
        session.add_all([genre_meow, genre_bark])
        await session.commit()

        star1 = StarModel(name="Talking Angela")
        star2 = StarModel(name="Talking Tom")
        session.add_all([star1, star2])
        await session.commit()

        director1 = DirectorModel(name="Kit Stepan")
        director2 = DirectorModel(name="Grumpy Cat")
        session.add_all([director1, director2])
        await session.commit()

        movie1 = MovieModel(
            name="Meowles of tomorrow",
            year=2023,
            time=130,
            imdb=8.7,
            votes=28000,
            meta_score=88,
            gross=120_000_000,
            description="A tense psychological thriller about time and memory.",
            price=Decimal("18.99"),
            certification_id=cert_pg13.id,
            genres=[genre_meow, genre_bark],
            stars=[star1, star2],
            directors=[director1],
        )

        movie2 = MovieModel(
            name="Silent Barks",
            year=2024,
            time=115,
            imdb=7.5,
            votes=16000,
            meta_score=74,
            gross=55_000_000,
            description="A heartfelt drama exploring love and loss through music.",
            price=Decimal("16.49"),
            certification_id=cert_pg13.id,
            genres=[genre_meow],
            stars=[star1],
            directors=[director2],
        )

        session.add_all([movie1, movie2])
        await session.commit()

        cart1 = CartModel(user_id=user1.id)
        cart2 = CartModel(user_id=user2.id)
        session.add_all([cart1, cart2])
        await session.commit()

        item1 = CartItemModel(cart_id=cart1.id, movie_id=movie1.id)
        item2 = CartItemModel(cart_id=cart1.id, movie_id=movie2.id)
        item3 = CartItemModel(cart_id=cart2.id, movie_id=movie2.id)
        session.add_all([item1, item2, item3])
        await session.commit()


if __name__ == "__main__":
    asyncio.run(create_sample_data())
