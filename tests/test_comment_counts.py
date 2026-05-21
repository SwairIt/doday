"""Tests for `comment_counts_for` + the 💬 badge in the task row."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.comments.service import comment_counts_for, create_comment
from app.tasks.service import create_task


async def _user(db_session: AsyncSession, email: str = "cc-owner@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_comment_counts_groups_by_task(db_session: AsyncSession) -> None:
    user = await _user(db_session, "cc-group@s.ru")
    t1 = await create_task(db_session, user.id, title="С обсуждением")
    t2 = await create_task(db_session, user.id, title="Тихая")
    await create_comment(db_session, user.id, task_id=t1.id, body="первый")
    await create_comment(db_session, user.id, task_id=t1.id, body="второй")

    counts = await comment_counts_for(db_session, [t1.id, t2.id])
    assert counts[t1.id] == 2
    # A task with no comments is simply absent from the result.
    assert t2.id not in counts


async def test_comment_counts_empty_input(db_session: AsyncSession) -> None:
    user = await _user(db_session, "cc-empty@s.ru")
    await create_task(db_session, user.id, title="x")
    assert await comment_counts_for(db_session, []) == {}


async def test_comment_badge_in_project_view(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    # Resolve the logged-in user, create a task in their Inbox, comment on it.
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    task = await create_task(db_session, user.id, title="Обсуждаемая задача")
    await create_comment(db_session, user.id, task_id=task.id, body="есть вопрос")

    # The project page (which passes comment_count_map) shows the 💬 chip.
    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    # The badge carries a unique title; the context-menu «Комментарии» item does not.
    assert "Комментариев: 1" in body
    assert "💬 1" in body


async def test_no_comment_badge_when_no_comments(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    task = await create_task(db_session, user.id, title="Молчаливая задача")

    from app.projects.service import get_project

    project = await get_project(db_session, user.id, task.project_id)
    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    # The task renders, but no comment badge (its unique «Комментариев:» title).
    assert "Молчаливая задача" in body
    assert "Комментариев:" not in body
