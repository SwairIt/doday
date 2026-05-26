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


async def test_subtask_counts_for(db_session: AsyncSession) -> None:
    from app.tasks.service import complete_task, subtask_counts_for

    user = await _user(db_session, "subs@s.ru")
    parent = await create_task(db_session, user.id, title="Родитель")
    s1 = await create_task(db_session, user.id, title="sub1", parent_task_id=parent.id)
    await create_task(db_session, user.id, title="sub2", parent_task_id=parent.id)
    await create_task(db_session, user.id, title="sub3", parent_task_id=parent.id)
    await complete_task(db_session, user.id, s1.id)

    counts = await subtask_counts_for(db_session, user.id, [parent.id])
    assert counts[parent.id] == (1, 3)


async def test_subtask_counts_absent_when_no_subtasks(db_session: AsyncSession) -> None:
    from app.tasks.service import subtask_counts_for

    user = await _user(db_session, "nosubs@s.ru")
    lonely = await create_task(db_session, user.id, title="Без подзадач")
    counts = await subtask_counts_for(db_session, user.id, [lonely.id])
    assert lonely.id not in counts


async def test_subtask_counts_empty_input(db_session: AsyncSession) -> None:
    from app.tasks.service import subtask_counts_for

    user = await _user(db_session, "emptysubs@s.ru")
    assert await subtask_counts_for(db_session, user.id, []) == {}


async def test_update_assigns_and_unassigns_self(db_session: AsyncSession) -> None:
    from app.tasks.models import Task
    from app.tasks.service import update_task

    user = await _user(db_session, "ctxassign@s.ru")
    t = await create_task(db_session, user.id, title="X")

    await update_task(db_session, user.id, t.id, assigned_to=user.id)
    refreshed = await db_session.get(Task, t.id)
    assert refreshed is not None and refreshed.assigned_to == user.id

    await update_task(db_session, user.id, t.id, assigned_to=None)
    cleared = await db_session.get(Task, t.id)
    assert cleared is not None and cleared.assigned_to is None


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


async def test_count_for_filter_matches_list(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime

    from app.filters.service import count_for_filter, list_for_filter

    user = await _user(db_session, "filt@s.ru")
    overdue = await create_task(db_session, user.id, title="старая")
    overdue.due_at = datetime(2020, 1, 1, tzinfo=UTC)
    await create_task(db_session, user.id, title="без даты")
    await db_session.commit()

    for slug in ("overdue", "no-date", "high-priority", "this-week"):
        listed = await list_for_filter(db_session, user.id, slug)
        counted = await count_for_filter(db_session, user.id, slug)
        assert counted == len(listed), slug
    assert await count_for_filter(db_session, user.id, "no-date") >= 1


async def test_sidebar_counts_has_assigned_key(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/projects/sidebar-counts")
    assert response.status_code == 200
    body = response.json()
    assert "assigned" in body
    assert isinstance(body["assigned"], int)
    for key in ("no_date", "high_priority", "this_week"):
        assert key in body
        assert isinstance(body[key], int)


async def test_sidebar_counts_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/api/projects/sidebar-counts")
    assert response.status_code == 401


async def test_bulk_assign_me(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.tasks.models import Task

    owner = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    t = await create_task(db_session, owner.id, title="bulk-assign-me")

    resp = await logged_in_client.post(
        "/doday/htmx/bulk", data={"action": "assign_me", "ids": [str(t.id)]}
    )
    assert resp.status_code == 200

    refreshed = await db_session.get(Task, t.id)
    assert refreshed is not None
    await db_session.refresh(refreshed)
    assert refreshed.assigned_to == owner.id


async def test_bulk_unassign(logged_in_client: AsyncClient, db_session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.tasks.models import Task

    owner = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    t = await create_task(db_session, owner.id, title="bulk-unassign")
    await _assign(db_session, t.id, owner.id)

    resp = await logged_in_client.post(
        "/doday/htmx/bulk", data={"action": "unassign", "ids": [str(t.id)]}
    )
    assert resp.status_code == 200

    refreshed = await db_session.get(Task, t.id)
    assert refreshed is not None
    await db_session.refresh(refreshed)
    assert refreshed.assigned_to is None


async def test_bulk_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.post("/doday/htmx/bulk", data={"action": "assign_me", "ids": []})
    assert resp.status_code == 401


async def test_assigned_view_anonymous_blocked(client: AsyncClient) -> None:
    response = await client.get("/doday/app/assigned")
    assert response.status_code == 401


async def test_assigned_view_renders_empty(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/assigned")
    assert response.status_code == 200
    assert "Назначено мне" in response.text
    assert "Тебе пока ничего не назначено" in response.text
