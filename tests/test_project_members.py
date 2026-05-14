"""Phase δ — ProjectMember + ProjectInvitation model sanity."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import ProjectInvitation, ProjectMember


async def test_project_members_table_exists(db_session: AsyncSession) -> None:
    rows = (await db_session.execute(select(ProjectMember))).scalars().all()
    assert isinstance(rows, list)


async def test_project_invitations_table_exists(db_session: AsyncSession) -> None:
    rows = (await db_session.execute(select(ProjectInvitation))).scalars().all()
    assert isinstance(rows, list)


async def test_add_member_idempotent(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from sqlalchemy import select as sa_select

    from app.auth.models import User
    from app.projects.membership import add_member, is_member, list_members
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(sa_select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    project = await create_project(db_session, user1.id, name="Shared", color="violet")
    await db_session.commit()

    await add_member(db_session, project.id, second_user.id, role="member")  # type: ignore[attr-defined]
    await add_member(db_session, project.id, second_user.id, role="member")  # idempotent
    members = await list_members(db_session, project.id)
    user2_rows = [m for m in members if m.user_id == second_user.id]  # type: ignore[attr-defined]
    assert len(user2_rows) == 1
    assert await is_member(db_session, project.id, second_user.id) is True  # type: ignore[attr-defined]


async def test_is_owner_distinguishes_roles(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from sqlalchemy import select as sa_select

    from app.auth.models import User
    from app.projects.membership import add_member, is_owner
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(sa_select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    project = await create_project(db_session, user1.id, name="Roles", color="violet")
    await db_session.commit()
    await add_member(db_session, project.id, user1.id, role="owner")
    await add_member(db_session, project.id, second_user.id, role="member")  # type: ignore[attr-defined]
    assert await is_owner(db_session, project.id, user1.id) is True
    assert await is_owner(db_session, project.id, second_user.id) is False  # type: ignore[attr-defined]


async def test_remove_member(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from sqlalchemy import select as sa_select

    from app.auth.models import User
    from app.projects.membership import add_member, is_member, remove_member
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(sa_select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    project = await create_project(db_session, user1.id, name="P", color="violet")
    await db_session.commit()
    await add_member(db_session, project.id, second_user.id)  # type: ignore[attr-defined]
    await remove_member(db_session, project.id, second_user.id)  # type: ignore[attr-defined]
    assert await is_member(db_session, project.id, second_user.id) is False  # type: ignore[attr-defined]


async def test_member_project_ids(
    db_session: AsyncSession, logged_in_client: object, second_user: object
) -> None:
    from sqlalchemy import select as sa_select

    from app.auth.models import User
    from app.projects.membership import add_member, member_project_ids
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(sa_select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    p1 = await create_project(db_session, user1.id, name="A", color="violet")
    p2 = await create_project(db_session, user1.id, name="B", color="sky")
    await db_session.commit()
    await add_member(db_session, p1.id, second_user.id)  # type: ignore[attr-defined]
    ids = await member_project_ids(db_session, second_user.id)  # type: ignore[attr-defined]
    assert p1.id in ids
    assert p2.id not in ids
