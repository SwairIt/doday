"""Tests for bulk «Назначить на участника» (action=assign_user)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member
from app.projects.service import create_project
from app.tasks.models import Task
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_bulk_assign_user(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    proj = await create_project(db_session, owner.id, name="Назнач-проект")
    await add_member(db_session, proj.id, second_user.id, role="member")
    t1 = await create_task(db_session, owner.id, title="A1", project_id=proj.id)
    t2 = await create_task(db_session, owner.id, title="A2", project_id=proj.id)

    resp = await logged_in_client.post(
        "/doday/htmx/bulk",
        data={
            "action": "assign_user",
            "assignee_id": str(second_user.id),
            "ids": [str(t1.id), str(t2.id)],
        },
    )
    assert resp.status_code == 200
    for tid in (t1.id, t2.id):
        row = await db_session.get(Task, tid)
        assert row is not None
        await db_session.refresh(row)
        assert row.assigned_to == second_user.id


async def test_bulk_assign_user_skips_non_member(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    """second_user is NOT a member of this project → assignment skipped, no crash."""
    owner = await _owner(db_session)
    solo = await create_project(db_session, owner.id, name="Соло")
    t = await create_task(db_session, owner.id, title="Solo", project_id=solo.id)

    resp = await logged_in_client.post(
        "/doday/htmx/bulk",
        data={"action": "assign_user", "assignee_id": str(second_user.id), "ids": [str(t.id)]},
    )
    assert resp.status_code == 200  # no crash
    row = await db_session.get(Task, t.id)
    assert row is not None
    await db_session.refresh(row)
    assert row.assigned_to is None  # unchanged — assignee not a member


async def test_bulk_assign_user_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.post(
        "/doday/htmx/bulk", data={"action": "assign_user", "assignee_id": "x", "ids": []}
    )
    assert resp.status_code == 401
