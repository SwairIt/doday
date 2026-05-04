"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Common base for all ORM models."""


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    # Force every asyncpg connection to UTC so `func.date(timestamptz_col)`
    # in queries matches Python's `datetime.now(UTC).date()` consistently —
    # otherwise we get off-by-one buckets in the early hours of any non-UTC
    # server timezone (e.g. MSK at 02:00 stores May 4 23:00 UTC but
    # Postgres-in-MSK extracts DATE = May 5).
    return create_async_engine(
        get_settings().database_url,
        future=True,
        connect_args={"server_settings": {"timezone": "UTC"}},
    )


@lru_cache(maxsize=1)
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped DB session."""
    async with get_session_maker()() as session:
        yield session
