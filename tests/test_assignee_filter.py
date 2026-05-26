"""Tests for the assignee-filter toolbar on the project board.

The filtering itself is client-side (Alpine) and exercised via Playwright; here
we only assert the server renders the filter UI for shared projects and omits it
for single-member ones, and that the current user's id is embedded for «Мои».
"""

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


async def test_filter_shown_for_shared_project(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    project = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, project.id, second_user.id, role="member")

    body = (await logged_in_client.get(f"/doday/app/projects/{project.slug}")).text
    assert "Исполнитель:" in body
    assert "Не назначено" in body
    # The current user's id is embedded so the «Мои» filter can match rows.
    assert str(owner.id) in body


async def test_filter_hidden_for_single_member_project(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    inbox = await ensure_inbox(db_session, owner.id)

    body = (await logged_in_client.get(f"/doday/app/projects/{inbox.slug}")).text
    # Single-member project: no assignee-filter dropdown.
    assert "Исполнитель:" not in body
