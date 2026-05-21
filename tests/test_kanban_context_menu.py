"""Kanban cards must expose data-project (and the kcard id) so the global
right-click context menu can target them. Dynamic menu behaviour is verified by
Playwright; here we only assert the server-rendered attributes."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.service import create_task


async def test_kanban_card_exposes_project_and_kcard_id(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    task = await create_task(db_session, user.id, title="Карточка на доске")

    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    body = (await logged_in_client.get(f"/app/projects/{project.slug}?view=kanban")).text
    assert f'id="kcard-{task.id}"' in body
    # data-project lets the context menu fetch that project's members for «Назначить на →».
    assert f'data-project="{task.project_id}"' in body
