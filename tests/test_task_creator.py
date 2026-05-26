"""The task detail panel shows «Создал: <member>» in shared projects, and omits
it in single-member (personal) projects."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member
from app.projects.service import create_project
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_creator_shown_in_shared_project(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    proj = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, proj.id, second_user.id, role="member")
    task = await create_task(db_session, owner.id, title="Кто добавил", project_id=proj.id)

    body = (await logged_in_client.get(f"/doday/htmx/tasks/{task.id}/detail")).text
    assert "Создал:" in body
    assert "logged-in@example.com" in body  # creator email rendered


async def test_creator_hidden_in_personal_project(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    task = await create_task(db_session, owner.id, title="Личная")  # Inbox (single-member)

    body = (await logged_in_client.get(f"/doday/htmx/tasks/{task.id}/detail")).text
    assert "Создано" in body  # the dates footer still renders
    assert "Создал:" not in body  # no creator line in a solo project


async def test_detail_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.get("/doday/htmx/tasks/00000000-0000-0000-0000-000000000000/detail")
    assert resp.status_code == 401
