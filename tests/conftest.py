"""
Pytest fixtures for Grid Backend tests.
"""

import asyncio
import os
import tempfile
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Create a temp file for SQLite test database
_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db_path = _test_db_file.name
_test_db_file.close()

# Set test environment - using SQLite
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"
os.environ["DEBUG_MODE"] = "true"
os.environ["DEBUG_USER"] = "testdebug"  # Debug user for testing
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["TICK_RATE_MS"] = "100"  # Faster ticks for testing

from grid_backend.database import Base, get_db
from grid_backend.main import app


# Create test database engine (SQLite)
test_engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,
)

test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    # Clean up tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Create an authenticated test client (debug user)."""
    # Register a debug user
    response = await client.post(
        "/api/auth/register",
        json={"username": "testdebug", "password": "testpassword123"},
    )
    assert response.status_code == 201

    # Login
    response = await client.post(
        "/api/auth/login",
        json={"username": "testdebug", "password": "testpassword123"},
    )
    assert response.status_code == 200
    token = response.json()["token"]

    # Set auth header
    client.headers["Authorization"] = f"Bearer {token}"

    return client
