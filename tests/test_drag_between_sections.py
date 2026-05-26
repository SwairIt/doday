"""The project list view wires a shared SortableJS group so tasks can be dragged
between sections; the section change is persisted via PATCH (already covered).
The drag itself is Playwright-verified — here we assert the group is wired and
that a section change persists through the existing PATCH endpoint."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.service import create_project
from app.sections.service import create_section
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_project_list_has_shared_drag_group(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="Drag-проект")
    await create_section(db_session, user.id, project_id=project.id, name="Секция 1")
    await create_task(db_session, user.id, title="x", project_id=project.id)

    body = (await logged_in_client.get(f"/doday/app/projects/{project.slug}")).text
    # A shared Sortable group scoped to the project enables cross-section drag.
    assert f"group: 'tasks-{project.id}'" in body


async def test_patch_moves_task_to_section(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The drag's onEnd PATCHes section_id — verify that endpoint moves the task."""
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="Drag-проект-2")
    section = await create_section(db_session, user.id, project_id=project.id, name="Цель")
    task = await create_task(db_session, user.id, title="двигаемая", project_id=project.id)
    assert task.section_id is None

    resp = await logged_in_client.patch(
        f"/api/tasks/{task.id}", json={"section_id": str(section.id)}
    )
    assert resp.status_code == 200
    assert resp.json()["section_id"] == str(section.id)

    # And null clears it back to no-section.
    resp2 = await logged_in_client.patch(f"/api/tasks/{task.id}", json={"section_id": None})
    assert resp2.status_code == 200
    assert resp2.json()["section_id"] is None
