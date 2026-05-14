"""Phase δ — permission boundary tests: non-members get 404."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_project(db_session: AsyncSession, email: str, name: str) -> tuple[object, object]:
    from app.auth.models import User
    from app.projects.service import create_project

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    project = await create_project(db_session, user.id, name=name, color="violet")
    await db_session.commit()
    return user, project


async def test_non_member_cannot_get_project(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_logged_in_client: AsyncClient
) -> None:
    _, project = await _make_project(db_session, "logged-in@example.com", "Private")
    r = await second_logged_in_client.patch(f"/api/projects/{project.id}", json={"name": "hacked"})
    assert r.status_code == 404


async def test_member_can_access_after_add(
    db_session: AsyncSession,
    logged_in_client: AsyncClient,
    second_logged_in_client: AsyncClient,
    second_user: object,
) -> None:
    from app.projects.membership import add_member

    _, project = await _make_project(db_session, "logged-in@example.com", "Shared")
    await add_member(db_session, project.id, second_user.id, role="member")  # type: ignore[attr-defined]
    r = await second_logged_in_client.patch(
        f"/api/projects/{project.id}", json={"name": "renamed by member"}
    )
    assert r.status_code == 200


async def test_member_cannot_delete_project(
    db_session: AsyncSession,
    logged_in_client: AsyncClient,
    second_logged_in_client: AsyncClient,
    second_user: object,
) -> None:
    from app.projects.membership import add_member

    _, project = await _make_project(db_session, "logged-in@example.com", "Shared2")
    await add_member(db_session, project.id, second_user.id, role="member")  # type: ignore[attr-defined]
    r = await second_logged_in_client.delete(f"/api/projects/{project.id}")
    assert r.status_code == 404


async def test_non_member_cannot_access_task(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_logged_in_client: AsyncClient
) -> None:
    from app.tasks.service import create_task

    user, project = await _make_project(db_session, "logged-in@example.com", "P")
    task = await create_task(db_session, user.id, title="secret", project_id=project.id)  # type: ignore[attr-defined]
    await db_session.commit()
    r = await second_logged_in_client.patch(f"/api/tasks/{task.id}", json={"title": "x"})
    assert r.status_code == 404


async def test_owner_sees_only_own_projects_in_list(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_logged_in_client: AsyncClient
) -> None:
    _, _ = await _make_project(db_session, "logged-in@example.com", "Mine")
    r = await second_logged_in_client.get("/api/projects")
    assert r.status_code == 200
    # GET /api/projects returns a bare list of project objects
    projects = r.json()
    names = [p["name"] for p in projects]
    assert "Mine" not in names
