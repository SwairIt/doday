"""Tests for Project model — basic round-trip + uniqueness constraints."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.models import Project


async def _make_user(db_session: AsyncSession, email: str = "u@school.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_project_round_trip(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    p = Project(user_id=user.id, name="Учёба", slug="ucheba", color="violet")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    assert p.id is not None
    assert p.is_inbox is False
    assert p.is_archived is False
    assert p.position == 0
    assert p.created_at.tzinfo is not None


async def test_project_slug_unique_per_user(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    db_session.add(Project(user_id=user.id, name="A", slug="a"))
    await db_session.commit()

    db_session.add(Project(user_id=user.id, name="A again", slug="a"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_project_inbox_unique_per_user(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    db_session.add(Project(user_id=user.id, name="Inbox", slug="inbox", is_inbox=True))
    await db_session.commit()

    db_session.add(Project(user_id=user.id, name="Inbox 2", slug="inbox-2", is_inbox=True))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_project_slug_can_repeat_across_users(db_session: AsyncSession) -> None:
    u1 = await _make_user(db_session, "a@s.ru")
    u2 = await _make_user(db_session, "b@s.ru")
    db_session.add(Project(user_id=u1.id, name="Work", slug="work"))
    db_session.add(Project(user_id=u2.id, name="Work", slug="work"))
    await db_session.commit()  # must not raise
