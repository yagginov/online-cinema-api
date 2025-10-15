from unittest.mock import AsyncMock, patch

import pytest
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, func, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from config import get_settings
from database import (
    UserGroup,
    get_db_contextmanager,
    reset_database,
)
from database.models import UserGroupEnum
from database.models.accounts import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
)
from database.models.base import Base
from database.populate import CSVDatabaseSeeder
from main import app
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager

TEST_DATABASE_URL_ASYNC = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"

test_async_engine = create_async_engine(TEST_DATABASE_URL_ASYNC, echo=False)
test_sync_engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)

TestAsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
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


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "order: Specify the order of test execution")
    config.addinivalue_line("markers", "unit: Unit tests")


@pytest_asyncio.fixture(scope="function")
async def client():
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender and S3 storage with test doubles.
    """

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db(request):
    """
    Reset the SQLite database before each test function, except for tests marked with 'e2e'.

    By default, this fixture ensures that the database is cleared and recreated before every
    test function to maintain test isolation. However, if the test is marked with 'e2e',
    the database reset is skipped to allow preserving state between end-to-end tests.
    """
    if "e2e" in request.keywords:
        yield
    else:
        await reset_database()
        yield


@pytest_asyncio.fixture(scope="session")
async def reset_db_once_for_e2e(request):
    """
    Reset the database once for end-to-end tests.

    This fixture is intended to be used for end-to-end tests at the session scope,
    ensuring the database is reset before running E2E tests.
    """
    await reset_database()


@pytest_asyncio.fixture(scope="session")
async def settings():
    """
    Provide application settings.

    This fixture returns the application settings by calling get_settings().
    """
    return get_settings()


@pytest_asyncio.fixture(scope="session")
async def e2e_client():
    """
    Provide an asynchronous HTTP client for end-to-end tests.

    This client is available at the session scope.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide an async database session for database interactions.

    This fixture yields an async session using `get_db_contextmanager`, ensuring that the session
    is properly closed after each test.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def e2e_db_session():
    """
    Provide an async database session for end-to-end tests.

    This fixture yields an async session using `get_db_contextmanager` at the session scope,
    ensuring that the same session is used throughout the E2E test suite.
    Note: Using a session-scoped DB session in async tests may lead to shared state between tests,
    so use this fixture with caution if tests run concurrently.
    """
    async with get_db_contextmanager() as session:
        yield session


# @pytest_asyncio.fixture(scope="function")
# async def seed_user_groups(db_session: AsyncSession):
#     """
#     Asynchronously seed the UserGroup table with default user groups.
#
#     This fixture inserts all user groups defined in UserGroupEnum into the database and commits the transaction.
#     It then yields the asynchronous database session for further testing.
#     """
#     groups = [{"name": group.value} for group in UserGroupEnum]
#     await db_session.execute(insert(UserGroup).values(groups))
#     await db_session.commit()
#     yield db_session


@pytest_asyncio.fixture(scope="function")
async def seed_database(db_session):
    """
    Seed the database with test data if it is empty.

    This fixture initializes a `CSVDatabaseSeeder` and ensures the test database is populated before
    running tests that require existing data.

    :param db_session: The async database session fixture.
    :type db_session: AsyncSession
    """
    settings = get_settings()
    seeder = CSVDatabaseSeeder(
        csv_file_path=str(settings.BASE_DIR / "database" / "seed_data" / "test_data.csv"),
        db_session=db_session,
    )

    if not await seeder.is_db_populated():
        await seeder.seed()

    yield db_session


@pytest_asyncio.fixture(scope="function")
async def jwt_manager() -> JWTAuthManagerInterface:
    """
    Asynchronous fixture to create a JWT authentication manager instance.

    This fixture retrieves the application settings via `get_settings()` and uses them to
    instantiate a `JWTAuthManager`. The manager is configured with the secret keys for
    access and refresh tokens, as well as the JWT signing algorithm specified in the settings.

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with the appropriate
        secret keys and algorithm.
    """
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )


@pytest_asyncio.fixture(scope="function")
async def seed_user_groups(db_session: AsyncSession):
    """
    Seed UserGroup table with default groups and return the created group objects.
    """
    groups = [UserGroup(name=group.value) for group in UserGroupEnum]
    db_session.add_all(groups)
    await db_session.commit()
    for group in groups:
        await db_session.refresh(group)
    yield groups


@pytest.fixture(autouse=True)
def mock_email_sending():
    with patch("notifications.emails.EmailSender._send_email", new_callable=AsyncMock) as mock:
        yield mock
