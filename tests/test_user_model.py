"""Basic ORM round-trip + uniqueness check for the User model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


async def test_user_can_be_persisted_and_loaded(db_session: AsyncSession) -> None:
    db_session.add(User(email="kid@school.ru", password_hash="argon2-fake"))
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "kid@school.ru"))
    saved = result.scalar_one()

    assert saved.id is not None
    assert saved.email == "kid@school.ru"
    assert saved.password_hash == "argon2-fake"
    assert saved.email_verified_at is None
    assert saved.created_at is not None
    assert saved.created_at.tzinfo is not None  # timezone-aware


async def test_user_email_is_unique(db_session: AsyncSession) -> None:
    db_session.add(User(email="dup@school.ru", password_hash="h1"))
    await db_session.commit()

    db_session.add(User(email="dup@school.ru", password_hash="h2"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
