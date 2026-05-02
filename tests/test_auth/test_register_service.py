"""Integration tests for register_user service (touches DB)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import EmailAlreadyExists, register_user


async def test_register_creates_user_with_hashed_password(db_session: AsyncSession) -> None:
    payload = RegisterIn(email="new@school.ru", password="strongpass123")
    user = await register_user(db_session, payload)

    assert user.id is not None
    assert user.email == "new@school.ru"
    assert user.password_hash.startswith("$argon2")
    assert user.email_verified_at is None


async def test_register_raises_on_duplicate_email(db_session: AsyncSession) -> None:
    payload = RegisterIn(email="dup@school.ru", password="strongpass123")
    await register_user(db_session, payload)

    with pytest.raises(EmailAlreadyExists):
        await register_user(db_session, payload)
