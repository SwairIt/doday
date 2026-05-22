"""Subtask-progress (X/Y) and comment (💬) badges now show on the Today and
Upcoming views (previously only on project/kanban)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.comments.service import create_comment
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_today_shows_subtask_badge(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    parent = await create_task(db_session, user.id, title="Родитель", due_at=datetime.now(UTC))
    await create_task(db_session, user.id, title="суб1", parent_task_id=parent.id)
    await create_task(db_session, user.id, title="суб2", parent_task_id=parent.id)

    body = (await logged_in_client.get("/app/today")).text
    assert "Подзадачи:" in body
    assert ">0/2</span>" in body


async def test_today_shows_comment_badge(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    task = await create_task(db_session, user.id, title="Обсуждаемая", due_at=datetime.now(UTC))
    await create_comment(db_session, user.id, task_id=task.id, body="заметка")

    body = (await logged_in_client.get("/app/today")).text
    assert "Комментариев:" in body
    assert "💬" in body


async def test_upcoming_shows_subtask_badge(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    due = datetime.now(UTC) + timedelta(days=2)
    parent = await create_task(db_session, user.id, title="Предстоит", due_at=due)
    await create_task(db_session, user.id, title="субА", parent_task_id=parent.id)

    body = (await logged_in_client.get("/app/upcoming")).text
    assert "Подзадачи:" in body
    assert ">0/1</span>" in body
