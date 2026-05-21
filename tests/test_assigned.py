"""Tests for the «Назначено мне» (assigned-to-me) cross-project view."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.service import (
    complete_task,
    count_assigned_to_user,
    create_task,
    list_assigned_to_user,
)


async def _user(db_session: AsyncSession, email: str = "owner@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def _assign(db_session: AsyncSession, task_id: object, assignee_id: object) -> None:
    from app.tasks.models import Task

    task = await db_session.get(Task, task_id)
    assert task is not None
    task.assigned_to = assignee_id  # type: ignore[assignment]
    await db_session.commit()


async def test_assigned_includes_open_assigned(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    t = await create_task(db_session, user.id, title="Назначенная")
    await _assign(db_session, t.id, user.id)

    result = await list_assigned_to_user(db_session, user.id)
    assert [task.id for task in result] == [t.id]


async def test_assigned_excludes_unassigned(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await create_task(db_session, user.id, title="Ничья")

    result = await list_assigned_to_user(db_session, user.id)
    assert result == []


async def test_assigned_excludes_completed(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    t = await create_task(db_session, user.id, title="Сделанная")
    await _assign(db_session, t.id, user.id)
    await complete_task(db_session, user.id, t.id)

    result = await list_assigned_to_user(db_session, user.id)
    assert result == []


async def test_assigned_excludes_non_member_project(db_session: AsyncSession) -> None:
    """A stale assignment in a project the user isn't a member of must not leak."""
    owner = await _user(db_session, "owner2@s.ru")
    outsider = await _user(db_session, "outsider@s.ru")
    t = await create_task(db_session, owner.id, title="Чужая")
    await _assign(db_session, t.id, outsider.id)

    # outsider is not a member of owner's inbox → sees nothing
    result = await list_assigned_to_user(db_session, outsider.id)
    assert result == []
    # owner is a member but the task is assigned to outsider → owner sees nothing
    assert await list_assigned_to_user(db_session, owner.id) == []


async def test_count_assigned_matches_list(db_session: AsyncSession) -> None:
    user = await _user(db_session, "counter@s.ru")
    assert await count_assigned_to_user(db_session, user.id) == 0
    t1 = await create_task(db_session, user.id, title="A")
    t2 = await create_task(db_session, user.id, title="B")
    await _assign(db_session, t1.id, user.id)
    await _assign(db_session, t2.id, user.id)
    assert await count_assigned_to_user(db_session, user.id) == 2
    # completing one drops the count
    await complete_task(db_session, user.id, t1.id)
    assert await count_assigned_to_user(db_session, user.id) == 1


async def test_count_assigned_excludes_non_member(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "cowner@s.ru")
    outsider = await _user(db_session, "coutsider@s.ru")
    t = await create_task(db_session, owner.id, title="Чужая")
    await _assign(db_session, t.id, outsider.id)
    assert await count_assigned_to_user(db_session, outsider.id) == 0


async def test_assignee_map_includes_member(db_session: AsyncSession) -> None:
    user = await _user(db_session, "amap@s.ru")
    t = await create_task(db_session, user.id, title="X")

    from app.projects.membership import assignee_map_for_project

    amap = await assignee_map_for_project(db_session, t.project_id)
    assert user.id in amap
    assert amap[user.id]["initial"] == "A"
    assert amap[user.id]["label"] == "amap@s.ru"
    assert amap[user.id]["color"]  # deterministic palette colour, non-empty


async def test_assignee_map_empty_for_unknown_project(db_session: AsyncSession) -> None:
    from uuid import uuid4

    from app.projects.membership import assignee_map_for_project

    assert await assignee_map_for_project(db_session, uuid4()) == {}


async def test_sidebar_counts_has_assigned_key(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/projects/sidebar-counts")
    assert response.status_code == 200
    body = response.json()
    assert "assigned" in body
    assert isinstance(body["assigned"], int)


async def test_sidebar_counts_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/api/projects/sidebar-counts")
    assert response.status_code == 401


async def test_assigned_view_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/app/assigned")
    assert response.status_code == 401


async def test_assigned_view_renders_empty(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/assigned")
    assert response.status_code == 200
    assert "Назначено мне" in response.text
    assert "Тебе пока ничего не назначено" in response.text
