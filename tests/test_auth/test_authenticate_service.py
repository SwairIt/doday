"""Tests for the authenticate service."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import (
    InvalidCredentials,
    authenticate,
    register_user,
)


async def _make_verified(db_session: AsyncSession, email: str = "kid@school.ru") -> None:
    user = await register_user(db_session, RegisterIn(email=email, password="strongpass123"))
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()


async def test_authenticate_correct_credentials(db_session: AsyncSession) -> None:
    await _make_verified(db_session)
    user = await authenticate(db_session, "kid@school.ru", "strongpass123")
    assert user.email == "kid@school.ru"


async def test_authenticate_wrong_password(db_session: AsyncSession) -> None:
    await _make_verified(db_session)
    with pytest.raises(InvalidCredentials):
        await authenticate(db_session, "kid@school.ru", "wrong")


async def test_authenticate_unknown_email(db_session: AsyncSession) -> None:
    with pytest.raises(InvalidCredentials):
        await authenticate(db_session, "nobody@school.ru", "anything")


async def test_authenticate_unverified_email_allowed(db_session: AsyncSession) -> None:
    # Soft verification: an unverified user can still authenticate.
    await register_user(
        db_session, RegisterIn(email="unverified@school.ru", password="strongpass123")
    )
    user = await authenticate(db_session, "unverified@school.ru", "strongpass123")
    assert user.email == "unverified@school.ru"
    assert user.email_verified_at is None


async def test_authenticate_lowercases_email(db_session: AsyncSession) -> None:
    await _make_verified(db_session)
    user = await authenticate(db_session, "KID@SCHOOL.RU", "strongpass123")
    assert user.email == "kid@school.ru"
