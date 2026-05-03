"""Tests for the onboarding-on-verify flow (Inbox + 4 sample tasks)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterIn
from app.auth.service import (
    mark_email_verified,
    provision_new_user,
    register_user,
)
from app.projects.models import Project
from app.tasks.models import Task

EXPECTED_SAMPLE_COUNT = 4


async def test_verify_seeds_inbox_and_samples(db_session: AsyncSession) -> None:
    user = await register_user(
        db_session, RegisterIn(email="onboard@school.ru", password="strongpass123")
    )

    await mark_email_verified(db_session, str(user.id))

    inboxes = (
        (
            await db_session.execute(
                select(Project).where(Project.user_id == user.id, Project.is_inbox.is_(True))
            )
        )
        .scalars()
        .all()
    )
    assert len(inboxes) == 1

    tasks = (
        (
            await db_session.execute(
                select(Task).where(Task.user_id == user.id).order_by(Task.position)
            )
        )
        .scalars()
        .all()
    )
    assert len(tasks) == EXPECTED_SAMPLE_COUNT
    assert all(t.project_id == inboxes[0].id for t in tasks)
    assert all(not t.is_completed for t in tasks)


async def test_provision_is_idempotent(db_session: AsyncSession) -> None:
    user = await register_user(
        db_session,
        RegisterIn(email="idem@school.ru", password="strongpass123"),
    )
    await mark_email_verified(db_session, str(user.id))

    await provision_new_user(db_session, user)

    tasks = (
        await db_session.execute(select(Task).where(Task.user_id == user.id))
    ).scalars().all()
    assert len(tasks) == EXPECTED_SAMPLE_COUNT


async def test_re_verify_does_not_re_seed(db_session: AsyncSession) -> None:
    user = await register_user(
        db_session,
        RegisterIn(email="reverify@school.ru", password="strongpass123"),
    )
    await mark_email_verified(db_session, str(user.id))

    user.email_verified_at = None
    await db_session.commit()

    await mark_email_verified(db_session, str(user.id))
    tasks = (
        await db_session.execute(select(Task).where(Task.user_id == user.id))
    ).scalars().all()
    assert len(tasks) == EXPECTED_SAMPLE_COUNT


async def test_provision_skips_when_already_done(db_session: AsyncSession) -> None:
    user = await register_user(
        db_session,
        RegisterIn(email="manual@school.ru", password="strongpass123"),
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()

    await provision_new_user(db_session, user)
    first = (
        await db_session.execute(select(Task).where(Task.user_id == user.id))
    ).scalars().all()
    assert len(first) == EXPECTED_SAMPLE_COUNT

    await provision_new_user(db_session, user)
    second = (
        await db_session.execute(select(Task).where(Task.user_id == user.id))
    ).scalars().all()
    assert len(second) == EXPECTED_SAMPLE_COUNT
