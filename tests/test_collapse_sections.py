"""The project page shows a «Свернуть секции» toggle when the project has
sections, and omits it otherwise. The collapse itself is Playwright-verified."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.sections.service import create_section
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_collapse_toggle_present_with_sections(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    task = await create_task(db_session, user.id, title="x")  # ensures Inbox project
    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    await create_section(db_session, user.id, project_id=project.id, name="Секция 1")

    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert "doday-sections-toggle" in body
    assert "Свернуть секции" in body


async def test_collapse_toggle_absent_without_sections(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    from app.projects.service import create_project

    project = await create_project(db_session, user.id, name="Без секций")
    await create_task(db_session, user.id, title="одна задача", project_id=project.id)

    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert "одна задача" in body
    assert "doday-sections-toggle" not in body
