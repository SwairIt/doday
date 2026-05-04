"""Tests for audience-specific starter tasks created on email verification."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password
from app.auth.service import provision_new_user
from app.projects.service import ensure_inbox
from app.tasks.service import list_tasks


async def _make_user(session: AsyncSession, audience: str | None) -> User:
    user = User(
        email=f"{audience or 'none'}@welcome.test",
        password_hash=hash_password("strongpass123"),
        audience=audience,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.parametrize(
    ("audience", "marker"),
    [
        ("school", "домашку"),
        ("company", "стендап"),
        ("personal", "воды"),
    ],
)
async def test_audience_specific_starter_tasks(
    db_session: AsyncSession, audience: str, marker: str
) -> None:
    user = await _make_user(db_session, audience)
    await provision_new_user(db_session, user)

    inbox = await ensure_inbox(db_session, user.id)
    tasks = await list_tasks(db_session, user.id, project_id=inbox.id, include_completed=True)
    titles = [t.title for t in tasks]
    assert any(marker in t for t in titles), f"expected {marker!r} in {titles!r}"


async def test_no_audience_falls_back_to_generic(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, None)
    await provision_new_user(db_session, user)

    inbox = await ensure_inbox(db_session, user.id)
    tasks = await list_tasks(db_session, user.id, project_id=inbox.id, include_completed=True)
    titles = [t.title for t in tasks]
    assert any("кликни кружок" in t for t in titles)


async def test_provisioning_is_idempotent(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "school")
    await provision_new_user(db_session, user)
    await provision_new_user(db_session, user)

    inbox = await ensure_inbox(db_session, user.id)
    tasks = await list_tasks(db_session, user.id, project_id=inbox.id, include_completed=True)
    assert len(tasks) == 5  # five starter tasks for school, no duplicates


async def test_school_starter_count(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "school")
    await provision_new_user(db_session, user)

    inbox = await ensure_inbox(db_session, user.id)
    tasks = await list_tasks(db_session, user.id, project_id=inbox.id, include_completed=True)
    assert len(tasks) == 5
