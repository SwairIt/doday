"""Per-project activity feed (?view=activity) — created/completed/comments by all
members, scoped to the project, with the actor's avatar."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.comments.service import create_comment
from app.projects.membership import add_member
from app.projects.service import create_project
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_activity_shows_member_events(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    shared = await create_project(db_session, owner.id, name="Командная лента")
    await add_member(db_session, shared.id, second_user.id, role="member")
    task = await create_task(db_session, owner.id, title="ОбщаяЗадача", project_id=shared.id)
    # A teammate comments — their email/avatar should appear in the feed.
    await create_comment(db_session, second_user.id, task_id=task.id, body="моё мнение")

    body = (await logged_in_client.get(f"/app/projects/{shared.slug}?view=activity")).text
    assert "ОбщаяЗадача" in body
    assert second_user.email in body  # comment author's avatar title
    assert "Активность" in body


async def test_activity_empty_state_ok(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="Пустая лента")

    resp = await logged_in_client.get(f"/app/projects/{project.slug}?view=activity")
    assert resp.status_code == 200
    assert "Пока нет активности" in resp.text


async def test_activity_excludes_other_projects(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    p1 = await create_project(db_session, user.id, name="Лента П1")
    p2 = await create_project(db_session, user.id, name="Лента П2")
    await create_task(db_session, user.id, title="ЗадачаИзП2", project_id=p2.id)

    body = (await logged_in_client.get(f"/app/projects/{p1.slug}?view=activity")).text
    assert "ЗадачаИзП2" not in body
