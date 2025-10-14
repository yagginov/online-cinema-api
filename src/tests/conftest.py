import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from database.models.accounts import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
)
from database.models.base import Base

TEST_DATABASE_URL_ASYNC = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"

test_async_engine = create_async_engine(TEST_DATABASE_URL_ASYNC, echo=False)
test_sync_engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)

TestAsyncSessionLocal = sessionmaker(
    bind=test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Створити event loop для всієї сесії тестів."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def sync_db_session():
    Base.metadata.create_all(test_sync_engine)

    session = Session(test_sync_engine)
    yield session

    session.close()
    Base.metadata.drop_all(test_sync_engine)


@pytest_asyncio.fixture
async def test_user_group(async_db_session: AsyncSession):
    group = UserGroup(name=UserGroupEnum.USER)
    async_db_session.add(group)
    await async_db_session.commit()
    await async_db_session.refresh(group)
    return group


@pytest_asyncio.fixture
async def test_user(async_db_session: AsyncSession, test_user_group: UserGroup):
    user = User.create(
        email="test@example.com",
        raw_password="TestPassword123!",
        group_id=test_user_group.id,
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def expired_activation_token(async_db_session: AsyncSession, test_user: User):
    token = ActivationToken(
        user_id=test_user.id,
        token="expired_activation_token_123",
        expires_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    async_db_session.add(token)
    await async_db_session.commit()
    await async_db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def valid_activation_token(async_db_session: AsyncSession, test_user: User):
    token = ActivationToken(
        user_id=test_user.id,
        token="valid_activation_token_456",
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    async_db_session.add(token)
    await async_db_session.commit()
    await async_db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def expired_password_reset_token(async_db_session: AsyncSession, test_user: User):
    token = PasswordResetToken(
        user_id=test_user.id,
        token="expired_password_reset_token_789",
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    async_db_session.add(token)
    await async_db_session.commit()
    await async_db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def expired_refresh_token(async_db_session: AsyncSession, test_user: User):
    token = RefreshToken(
        user_id=test_user.id,
        token="expired_refresh_token_abc",
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    async_db_session.add(token)
    await async_db_session.commit()
    await async_db_session.refresh(token)
    return token
