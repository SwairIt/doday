"""The kanban board's assignee-filter toolbar must render for shared projects
(>1 member) and be absent for single-member ones. Client-side filtering is
verified by Playwright; here we assert the server-rendered toolbar."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member
from app.projects.service import create_project, ensure_inbox


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_kanban_filter_shown_for_shared_project(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    project = await create_project(db_session, owner.id, name="Доска команды")
    await add_member(db_session, project.id, second_user.id, role="member")

    body = (await logged_in_client.get(f"/app/projects/{project.slug}?view=kanban")).text
    assert "applyKanbanAssigneeFilter" in body
    assert "Не назначено" in body
    assert str(owner.id) in body  # current_user.id embedded for the «Мои» filter


async def test_kanban_filter_hidden_for_single_member(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    inbox = await ensure_inbox(db_session, owner.id)

    body = (await logged_in_client.get(f"/app/projects/{inbox.slug}?view=kanban")).text
    # Single-member project: no assignee-filter toolbar.
    assert "doday-kanban-assignee-filter" not in body
