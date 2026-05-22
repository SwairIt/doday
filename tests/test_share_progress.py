"""Public read-only progress-share links.

Two layers: the signed-token round-trip (no DB), and the no-auth
`/share/progress/<token>` HTML view a parent opens without an account.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import hash_password
from app.share.service import (
    InvalidShareToken,
    make_group_token,
    make_progress_token,
    read_group_token,
    read_progress_token,
)
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


def test_token_roundtrip() -> None:
    uid = uuid4()
    assert read_progress_token(make_progress_token(uid)) == uid


def test_bad_token_rejected() -> None:
    with pytest.raises(InvalidShareToken):
        read_progress_token("not-a-real-token")


def test_tampered_token_rejected() -> None:
    token = make_progress_token(uuid4())
    with pytest.raises(InvalidShareToken):
        read_progress_token(token + "x")


async def test_progress_view_is_public_and_shows_tasks(
    client: AsyncClient, logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A parent with the signed link sees the child's day WITHOUT logging in."""
    user = await _owner(db_session)
    await create_task(db_session, user.id, title="Прочитать главу 5", due_at=datetime.now(UTC))
    token = make_progress_token(user.id)

    # `client` is unauthenticated — proves the route does not require auth.
    resp = await client.get(f"/share/progress/{token}")
    assert resp.status_code == 200
    assert "Прочитать главу 5" in resp.text


async def test_progress_view_bad_token_404(client: AsyncClient) -> None:
    resp = await client.get("/share/progress/garbage")
    assert resp.status_code == 404


async def test_share_link_endpoint_returns_url(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.get("/api/profile/share-link")
    assert resp.status_code == 200
    assert "/share/progress/" in resp.json()["url"]


# --- Group (class) progress link -------------------------------------------


def test_group_token_roundtrip() -> None:
    pid = uuid4()
    assert read_group_token(make_group_token(pid)) == pid


async def test_group_view_public_shows_members(
    client: AsyncClient, logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.projects.membership import add_member
    from app.projects.service import create_project

    owner = await _owner(db_session)
    project = await create_project(db_session, owner.id, name="Класс 9А")

    student = User(email="student1@example.com", password_hash=hash_password("x" * 10))
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    await add_member(db_session, project.id, student.id)

    task = await create_task(
        db_session, owner.id, title="ДЗ параграф 5", project_id=project.id, due_at=datetime.now(UTC)
    )
    task.assigned_to = student.id
    await db_session.commit()

    resp = await client.get(f"/share/group/{make_group_token(project.id)}")
    assert resp.status_code == 200
    assert "Класс 9А" in resp.text
    assert "student1@example.com" in resp.text


async def test_group_view_bad_token_404(client: AsyncClient) -> None:
    resp = await client.get("/share/group/garbage")
    assert resp.status_code == 404


async def test_group_share_link_requires_membership(
    client: AsyncClient, logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.projects.service import create_project

    owner = await _owner(db_session)
    project = await create_project(db_session, owner.id, name="Группа")

    resp = await logged_in_client.get(f"/api/projects/{project.id}/group-share-link")
    assert resp.status_code == 200
    assert "/share/group/" in resp.json()["url"]
