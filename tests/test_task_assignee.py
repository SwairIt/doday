"""Phase δ — task assignee (assigned_to) field."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _project_and_task(db_session: AsyncSession, email: str):
    from app.auth.models import User
    from app.projects.service import create_project
    from app.tasks.service import create_task

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    project = await create_project(db_session, user.id, name="Assign", color="violet")
    task = await create_task(db_session, user.id, title="Task", project_id=project.id)
    await db_session.commit()
    return user, project, task


async def test_assign_task_to_member(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_user
) -> None:
    from app.projects.membership import add_member

    _user, project, task = await _project_and_task(db_session, "logged-in@example.com")
    await add_member(db_session, project.id, second_user.id, role="member")
    await db_session.commit()
    r = await logged_in_client.patch(
        f"/api/tasks/{task.id}", json={"assigned_to": str(second_user.id)}
    )
    assert r.status_code == 200
    assert r.json()["assigned_to"] == str(second_user.id)


async def test_assign_to_non_member_rejected(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_user
) -> None:
    _user, _project, task = await _project_and_task(db_session, "logged-in@example.com")
    # second_user is NOT a member of the project
    r = await logged_in_client.patch(
        f"/api/tasks/{task.id}", json={"assigned_to": str(second_user.id)}
    )
    assert r.status_code == 400


async def test_clear_assignee(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_user
) -> None:
    from app.projects.membership import add_member

    _user, project, task = await _project_and_task(db_session, "logged-in@example.com")
    await add_member(db_session, project.id, second_user.id, role="member")
    await db_session.commit()
    await logged_in_client.patch(f"/api/tasks/{task.id}", json={"assigned_to": str(second_user.id)})
    r = await logged_in_client.patch(f"/api/tasks/{task.id}", json={"assigned_to": None})
    assert r.status_code == 200
    assert r.json()["assigned_to"] is None
