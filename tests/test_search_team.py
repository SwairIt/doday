"""Search must find teammates' tasks in shared projects (scoped by membership),
not just tasks the searcher created — without leaking non-member projects."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.membership import add_member
from app.projects.service import create_project
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_search_finds_teammate_task_in_shared_project(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    owner = await _owner(db_session)
    shared = await create_project(db_session, owner.id, name="Командный")
    await add_member(db_session, shared.id, second_user.id, role="member")
    # Task authored by the teammate (different creator) in the shared project.
    await create_task(db_session, second_user.id, title="зюзюблик напарника", project_id=shared.id)
    # And one the owner created.
    await create_task(db_session, owner.id, title="зюзюблик мой", project_id=shared.id)

    resp = await logged_in_client.get("/doday/htmx/search?q=зюзюблик&format=json")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["tasks"]]
    assert "зюзюблик напарника" in titles  # previously invisible to search
    assert "зюзюблик мой" in titles


async def test_search_excludes_non_member_project(
    logged_in_client: AsyncClient, db_session: AsyncSession, second_user: Any
) -> None:
    # A project the owner is NOT a member of — its tasks must not surface.
    foreign = await create_project(db_session, second_user.id, name="Чужой")
    await create_task(db_session, second_user.id, title="квакозябрь", project_id=foreign.id)

    resp = await logged_in_client.get("/doday/htmx/search?q=квакозябрь&format=json")
    assert resp.status_code == 200
    assert resp.json()["tasks"] == []


async def test_search_anonymous_blocked(client: AsyncClient) -> None:
    resp = await client.get("/doday/htmx/search?q=test")
    assert resp.status_code == 401
