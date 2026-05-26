"""Tests for bulk «Перенести в секцию» (action=set_section)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import create_project
from app.sections.service import create_section
from app.tasks.models import Task
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_bulk_set_and_clear_section(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    proj = await create_project(db_session, user.id, name="Секц-проект")
    section = await create_section(db_session, user.id, project_id=proj.id, name="Колонка")
    t1 = await create_task(db_session, user.id, title="S1", project_id=proj.id)
    t2 = await create_task(db_session, user.id, title="S2", project_id=proj.id)

    resp = await logged_in_client.post(
        "/doday/htmx/bulk",
        data={
            "action": "set_section",
            "section_id": str(section.id),
            "ids": [str(t1.id), str(t2.id)],
        },
    )
    assert resp.status_code == 200
    for tid in (t1.id, t2.id):
        row = await db_session.get(Task, tid)
        assert row is not None
        await db_session.refresh(row)
        assert row.section_id == section.id

    # Empty section_id clears the section.
    resp2 = await logged_in_client.post(
        "/doday/htmx/bulk",
        data={"action": "set_section", "section_id": "", "ids": [str(t1.id)]},
    )
    assert resp2.status_code == 200
    row = await db_session.get(Task, t1.id)
    assert row is not None
    await db_session.refresh(row)
    assert row.section_id is None


async def test_bulk_set_section_skips_foreign_project(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A section from project A can't be applied to a task in project B — skipped, no crash."""
    user = await _owner(db_session)
    proj_a = await create_project(db_session, user.id, name="A")
    section_a = await create_section(db_session, user.id, project_id=proj_a.id, name="SecA")
    proj_b = await create_project(db_session, user.id, name="B")
    t_b = await create_task(db_session, user.id, title="InB", project_id=proj_b.id)

    resp = await logged_in_client.post(
        "/doday/htmx/bulk",
        data={"action": "set_section", "section_id": str(section_a.id), "ids": [str(t_b.id)]},
    )
    assert resp.status_code == 200  # no crash
    row = await db_session.get(Task, t_b.id)
    assert row is not None
    await db_session.refresh(row)
    assert row.section_id is None  # unchanged — mismatched project skipped


async def test_bulk_set_section_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.post("/doday/htmx/bulk", data={"action": "set_section", "ids": []})
    assert resp.status_code == 401
