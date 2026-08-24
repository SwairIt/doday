"""Tests for the «Назначить на → участника» context-menu item.

The dynamic member submenu is client-side (Playwright-verified); here we only
assert the server renders the menu item and exposes the task's project id on the
row so the menu can fetch that project's members.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.service import create_task


async def test_assign_member_item_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # The context menu (included on every /app page) carries the new item.
    assert 'data-ctx="assign-member"' in body
    assert "Назначить на" in body


async def test_task_row_exposes_project(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    task = await create_task(db_session, user.id, title="С проектом в data-атрибуте")

    body = (await logged_in_client.get("/app/projects/inbox")).text
    # The row carries data-project so the menu knows which project's members to fetch.
    assert f'data-project="{task.project_id}"' in body
