"""Service-level tests for sections."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import create_project
from app.sections.service import (
    SectionNotFound,
    create_section,
    delete_section,
    get_section,
    list_sections,
    update_section,
)


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_create_section_assigns_position(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="Work")
    s1 = await create_section(db_session, user.id, project_id=proj.id, name="Todo")
    s2 = await create_section(db_session, user.id, project_id=proj.id, name="Doing")
    assert s1.position == 0
    assert s2.position == 1


async def test_list_sections_orders_by_position(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="X")
    await create_section(db_session, user.id, project_id=proj.id, name="A")
    await create_section(db_session, user.id, project_id=proj.id, name="B")

    sections = await list_sections(db_session, user.id, proj.id)
    assert [s.name for s in sections] == ["A", "B"]


async def test_get_section_isolated_per_user(db_session: AsyncSession) -> None:
    u1 = await _user(db_session, "a@s.ru")
    u2 = await _user(db_session, "b@s.ru")
    p1 = await create_project(db_session, u1.id, name="P1")
    s = await create_section(db_session, u1.id, project_id=p1.id, name="S")

    fetched = await get_section(db_session, u1.id, s.id)
    assert fetched.id == s.id

    with pytest.raises(SectionNotFound):
        await get_section(db_session, u2.id, s.id)


async def test_update_section_renames(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="P")
    s = await create_section(db_session, user.id, project_id=proj.id, name="Old")
    s2 = await update_section(db_session, user.id, s.id, name="New")
    assert s2.name == "New"


async def test_delete_section_keeps_tasks(db_session: AsyncSession) -> None:
    """Deleting a section sets tasks.section_id to NULL, doesn't drop them."""
    from app.tasks.service import create_task, list_tasks

    user = await _user(db_session)
    proj = await create_project(db_session, user.id, name="P")
    section = await create_section(db_session, user.id, project_id=proj.id, name="S")
    task = await create_task(
        db_session, user.id, project_id=proj.id, section_id=section.id, title="T"
    )

    await delete_section(db_session, user.id, section.id)

    tasks = await list_tasks(db_session, user.id, project_id=proj.id)
    assert len(tasks) == 1
    await db_session.refresh(task)
    assert task.section_id is None
