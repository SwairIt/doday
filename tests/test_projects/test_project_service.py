"""Service-level tests for projects (no HTTP)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import (
    CannotDeleteInbox,
    ProjectNotFound,
    create_project,
    delete_project,
    ensure_inbox,
    get_project,
    list_projects,
    slugify,
    update_project,
)


async def _make_user(db_session: AsyncSession, email: str = "u@school.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


def test_slugify_ascii() -> None:
    s = slugify("Work In Progress")
    assert s.startswith("work-in-progress-")


def test_slugify_cyrillic_falls_back() -> None:
    s = slugify("Учёба")
    assert s.startswith("p-")


def test_slugify_empty_falls_back() -> None:
    s = slugify("...")
    assert s.startswith("p-")


async def test_create_project_assigns_position(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    p1 = await create_project(db_session, user.id, name="A")
    p2 = await create_project(db_session, user.id, name="B")
    assert p1.position == 0
    assert p2.position == 1
    assert p1.slug != p2.slug


async def test_list_projects_excludes_archived(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    await create_project(db_session, user.id, name="Active")
    archived = await create_project(db_session, user.id, name="Done")
    await update_project(db_session, user.id, archived.id, is_archived=True)

    projects = await list_projects(db_session, user.id)
    assert [p.name for p in projects] == ["Active"]


async def test_get_project_isolated_per_user(db_session: AsyncSession) -> None:
    u1 = await _make_user(db_session, "a@s.ru")
    u2 = await _make_user(db_session, "b@s.ru")
    p = await create_project(db_session, u1.id, name="Mine")

    fetched = await get_project(db_session, u1.id, p.id)
    assert fetched.id == p.id

    with pytest.raises(ProjectNotFound):
        await get_project(db_session, u2.id, p.id)


async def test_update_project(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    p = await create_project(db_session, user.id, name="Old")

    p2 = await update_project(db_session, user.id, p.id, name="New", color="rose")
    assert p2.name == "New"
    assert p2.color == "rose"


async def test_delete_project(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    p = await create_project(db_session, user.id, name="To delete")
    await delete_project(db_session, user.id, p.id)

    with pytest.raises(ProjectNotFound):
        await get_project(db_session, user.id, p.id)


async def test_cannot_delete_inbox(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    inbox = await ensure_inbox(db_session, user.id)
    with pytest.raises(CannotDeleteInbox):
        await delete_project(db_session, user.id, inbox.id)


async def test_ensure_inbox_idempotent(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    a = await ensure_inbox(db_session, user.id)
    b = await ensure_inbox(db_session, user.id)
    assert a.id == b.id
    assert a.is_inbox is True
