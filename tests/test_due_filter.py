"""The project page exposes a «Срок» (due) filter chip. Filtering itself is
Playwright-verified."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import create_project
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_due_filter_present_on_project_page(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="Со сроками")
    await create_task(db_session, user.id, title="задача", project_id=project.id)

    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert "setDueFilter('all')" in body
    assert "doday-due-filter" in body
    assert "Просрочено" in body
    assert "Сегодня" in body
