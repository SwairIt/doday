"""The task row shows a 📝 description-preview toggle (with JSON-embedded text)
only for tasks that have a description. Markdown rendering/toggle is verified by
Playwright; here we assert the server-rendered marker."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_description_preview_present(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    task = await create_task(
        db_session, user.id, title="С заметкой", description="**важная** деталь"
    )

    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert f'id="desc-data-{task.id}"' in body
    assert "Показать описание" in body


async def test_no_description_preview_when_empty(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    task = await create_task(db_session, user.id, title="Без заметки")

    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert "Без заметки" in body
    assert f'id="desc-data-{task.id}"' not in body
