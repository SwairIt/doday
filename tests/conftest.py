"""Shared pytest fixtures.

Schema setup happens once per test session against TEST_DATABASE_URL.
Between every test function, ALL tables are TRUNCATEd to start clean —
not rolled back, because app code calls .commit() during normal flow.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth import models as _auth_models  # noqa: F401  register tables with Base.metadata
from app.config import get_settings
from app.db import Base, get_session
from app.labels import models as _labels_models  # noqa: F401
from app.main import app
from app.projects import models as _projects_models  # noqa: F401
from app.sections import models as _sections_models  # noqa: F401
from app.tasks import models as _tasks_models  # noqa: F401

_settings = get_settings()


async def _setup_test_schema() -> None:
    test_engine = create_async_engine(_settings.test_database_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _init_test_db() -> None:
    asyncio.run(_setup_test_schema())


async def _truncate_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    test_engine = create_async_engine(_settings.test_database_url)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await _truncate_all(test_engine)
    await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def logged_in_client(client: AsyncClient, db_session: AsyncSession) -> AsyncClient:
    """A client with a freshly verified user logged in (cookie set)."""
    from datetime import UTC, datetime

    from app.auth.schemas import RegisterIn
    from app.auth.service import register_user

    user = await register_user(
        db_session,
        RegisterIn(email="logged-in@example.com", password="strongpass123"),
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        "/auth/login",
        data={"email": "logged-in@example.com", "password": "strongpass123"},
    )
    assert response.status_code == 303
    return client
