"""Tests for the per-label task view (/doday/app/labels/{id}) and its service query."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.labels.service import attach_label, create_label, list_tasks_by_label
from app.tasks.service import complete_task, create_task


async def _user(db_session: AsyncSession, email: str) -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_list_tasks_by_label_returns_tagged(db_session: AsyncSession) -> None:
    user = await _user(db_session, "lbl1@s.ru")
    label = await create_label(db_session, user.id, name="work")
    tagged = await create_task(db_session, user.id, title="С лейблом")
    await create_task(db_session, user.id, title="Без лейбла")
    await attach_label(db_session, user.id, tagged.id, label.id)

    result = await list_tasks_by_label(db_session, user.id, label.id)
    assert [t.id for t in result] == [tagged.id]


async def test_list_tasks_by_label_excludes_completed(db_session: AsyncSession) -> None:
    user = await _user(db_session, "lbl2@s.ru")
    label = await create_label(db_session, user.id, name="done-test")
    t = await create_task(db_session, user.id, title="Закрою")
    await attach_label(db_session, user.id, t.id, label.id)
    await complete_task(db_session, user.id, t.id)

    assert await list_tasks_by_label(db_session, user.id, label.id) == []


async def test_label_view_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/doday/app/labels/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


async def test_label_view_renders_with_dict_filter(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Label view reuses filter.html with a dict 'filter' (no .slug) — must not crash."""
    from sqlalchemy import select

    owner = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    label = await create_label(db_session, owner.id, name="render-test")

    resp = await logged_in_client.get(f"/doday/app/labels/{label.id}")
    assert resp.status_code == 200
    assert "@render-test" in resp.text
