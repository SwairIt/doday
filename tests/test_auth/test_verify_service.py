"""Tests for the mark_email_verified service."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import TokenInvalid, mark_email_verified, register_user


async def test_mark_email_verified_sets_timestamp(db_session: AsyncSession) -> None:
    user = await register_user(
        db_session, RegisterIn(email="kid@school.ru", password="strongpass123")
    )
    assert user.email_verified_at is None

    updated = await mark_email_verified(db_session, str(user.id))
    assert updated.email_verified_at is not None


async def test_mark_email_verified_unknown_user_raises(db_session: AsyncSession) -> None:
    with pytest.raises(TokenInvalid):
        await mark_email_verified(db_session, str(uuid4()))


async def test_mark_email_verified_malformed_id_raises(db_session: AsyncSession) -> None:
    with pytest.raises(TokenInvalid):
        await mark_email_verified(db_session, "not-a-uuid")
