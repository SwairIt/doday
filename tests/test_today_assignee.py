"""Assignee avatars on the cross-project Today/Upcoming lists.

`assignee_map_for_projects` merges members across projects, and `today_view`
passes a map covering shared-project tasks so a teammate's avatar shows up.
"""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member, assignee_map_for_projects
from app.projects.service import create_project
from app.tasks.service import create_task, update_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def _make_user(db_session: AsyncSession, email: str) -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


async def test_assignee_map_for_projects_merges(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session, "merge-owner@s.ru")
    other = await _make_user(db_session, "merge-other@s.ru")
    p1 = await create_project(db_session, owner.id, name="P1")
    p2 = await create_project(db_session, owner.id, name="P2")
    await add_member(db_session, p2.id, other.id, role="member")

    merged = await assignee_map_for_projects(db_session, [p1.id, p2.id])
    assert owner.id in merged
    assert other.id in merged
    assert merged[other.id]["label"] == "merge-other@s.ru"


async def test_assignee_map_for_projects_empty(db_session: AsyncSession) -> None:
    assert await assignee_map_for_projects(db_session, []) == {}


async def test_today_shows_shared_assignee_avatar(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    shared = await create_project(db_session, owner.id, name="Командный today")
    await add_member(db_session, shared.id, second_user.id, role="member")
    task = await create_task(
        db_session,
        owner.id,
        title="общая на сегодня",
        project_id=shared.id,
        due_at=datetime.now(UTC),
    )
    await update_task(db_session, owner.id, task.id, assigned_to=second_user.id)

    body = (await logged_in_client.get("/app/today")).text
    # The assignee (second_user) appears as an avatar (label in the title attr).
    assert second_user.email in body


async def test_today_personal_task_has_no_assignee_avatar(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    solo = await create_project(db_session, user.id, name="Личный today")
    await create_task(
        db_session,
        user.id,
        title="личная на сегодня",
        project_id=solo.id,
        due_at=datetime.now(UTC),
    )

    resp = await logged_in_client.get("/app/today")
    assert resp.status_code == 200
    # Personal single-member project → no assignee avatar markup for it.
    assert "Исполнитель:" not in resp.text
