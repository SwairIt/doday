"""Tests for the «Команда» team-workload view (/doday/app/team) and list_team_tasks."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member
from app.projects.service import create_project, ensure_inbox
from app.tasks.service import complete_task, create_task, delete_task, list_team_tasks


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


async def test_team_tasks_only_from_shared_projects(
    db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _make_user(db_session, "team-owner-1@s.ru")
    # A shared project (owner + second_user) with a task.
    shared = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, shared.id, second_user.id, role="member")
    t_shared = await create_task(db_session, owner.id, title="Общая", project_id=shared.id)
    # A personal (single-member) project with a task — must be excluded.
    solo = await create_project(db_session, owner.id, name="Личный")
    await create_task(db_session, owner.id, title="Личная", project_id=solo.id)

    tasks = await list_team_tasks(db_session, owner.id)
    ids = {t.id for t in tasks}
    assert t_shared.id in ids
    assert all(t.project_id == shared.id for t in tasks)


async def test_team_tasks_exclude_completed_and_trashed(
    db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _make_user(db_session, "team-owner-2@s.ru")
    shared = await create_project(db_session, owner.id, name="Командный2")
    await add_member(db_session, shared.id, second_user.id, role="member")
    open_t = await create_task(db_session, owner.id, title="Открытая", project_id=shared.id)
    done_t = await create_task(db_session, owner.id, title="Готовая", project_id=shared.id)
    trash_t = await create_task(db_session, owner.id, title="Удалённая", project_id=shared.id)
    await complete_task(db_session, owner.id, done_t.id)
    await delete_task(db_session, owner.id, trash_t.id)

    ids = {t.id for t in await list_team_tasks(db_session, owner.id)}
    assert open_t.id in ids
    assert done_t.id not in ids
    assert trash_t.id not in ids


async def test_team_view_renders(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    shared = await create_project(db_session, owner.id, name="Командный3")
    await add_member(db_session, shared.id, second_user.id, role="member")
    await create_task(db_session, owner.id, title="Видна в команде", project_id=shared.id)

    resp = await logged_in_client.get("/doday/app/team")
    assert resp.status_code == 200
    assert "Команда" in resp.text
    assert "Видна в команде" in resp.text


async def test_team_view_empty_state(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    await ensure_inbox(db_session, owner.id)  # only a personal project → no team tasks
    resp = await logged_in_client.get("/doday/app/team")
    assert resp.status_code == 200
    assert "появятся задачи команды" in resp.text


async def test_team_view_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.get("/doday/app/team")
    assert resp.status_code == 401
