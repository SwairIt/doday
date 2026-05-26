"""The 💬 comment badge must render on the cross-project teams hubs
(/doday/app/team and /doday/app/assigned), not just project/kanban views."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.comments.service import create_comment
from app.projects.membership import add_member
from app.projects.service import create_project
from app.tasks.service import create_task, update_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_comment_badge_on_assigned_view(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    task = await create_task(db_session, owner.id, title="Назначенная с обсуждением")
    await update_task(db_session, owner.id, task.id, assigned_to=owner.id)
    await create_comment(db_session, owner.id, task_id=task.id, body="вопрос по задаче")

    body = (await logged_in_client.get("/doday/app/assigned")).text
    assert "Назначенная с обсуждением" in body
    assert "Комментариев: 1" in body


async def test_comment_badge_on_team_view(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    shared = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, shared.id, second_user.id, role="member")
    task = await create_task(
        db_session, owner.id, title="Командная с обсуждением", project_id=shared.id
    )
    await create_comment(db_session, owner.id, task_id=task.id, body="обсуждаем")

    body = (await logged_in_client.get("/doday/app/team")).text
    assert "Командная с обсуждением" in body
    assert "Комментариев: 1" in body


async def test_no_badge_without_comments_on_assigned(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _owner(db_session)
    task = await create_task(db_session, owner.id, title="Тихая назначенная")
    await update_task(db_session, owner.id, task.id, assigned_to=owner.id)

    body = (await logged_in_client.get("/doday/app/assigned")).text
    assert "Тихая назначенная" in body
    assert "Комментариев:" not in body
