# Phase δ — Team collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Shared projects в Todoist-стиле — owner приглашает по email, инвайт-письмо → ссылка → join, member видит проект и работает с задачами. Permission-слой + assignee на задачах.

**Architecture:** Ключевое открытие recon — ownership проверяется централизованно в 3 service-функциях (`get_project`, `get_task`, `get_section`), все ~40 endpoints зовут их. Permission-gate встраивается в эти 3 функции + `list_projects` — не переписываем роутеры. Личные views (Today/Upcoming) остаются личными (`task.user_id == me OR task.assigned_to == me`); project-view показывает все задачи проекта членам.

**Tech Stack:** FastAPI + async SQLAlchemy 2.0 + Alembic + aiosmtplib + Jinja2. Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`.

---

## Recon facts (2026-05-14)

- **Auth:** cookie-session, `RequiredUser` (raises 401), `CurrentUser` (`User|None`), `DbSession`. `app/auth/deps.py`.
- **Ownership pattern (UNIVERSAL):** `get_project(session, user_id, project_id)` — PK lookup + `if project.user_id != user_id: raise ProjectNotFound`. Identical for `get_task`, `get_section`. Every router calls service funcs with `user.id`. NO raw `session.get()` in routers.
- **`list_projects(session, user_id)`** — `WHERE user_id = user_id`.
- **`list_today/upcoming/...`** — `WHERE Task.user_id = user_id`.
- **Project:** `id, user_id (FK users CASCADE), name, slug, color, position, is_inbox, is_archived, is_favorite, description`.
- **Task:** `id, user_id, project_id, parent_task_id, section_id, title, ..., priority, is_completed, deleted_at`.
- **Section:** has both `project_id` AND `user_id` FK (CASCADE).
- **Migrations:** latest `0029`. Style: numeric string ids, `down_revision`, `downgrade()` raises for one-way.
- **Email:** `app/auth/email.py`, `aiosmtplib`, `send_verification_email(*, to, verification_url)`. Body built via Python string funcs `_render_html()`/`_render_text()` — NO Jinja email templates. SMTP settings: `app/config.py` `smtp_*`.
- **User:** `email` globally unique. `get_user_by_email(session, email)` exists in `app/auth/service.py`.
- **Tests:** `tests/conftest.py` — `db_session`, `client`, `logged_in_client` ("logged-in@example.com"). NO second-user fixture. TRUNCATE-between-tests (not rollback).

---

## Permission model

- Roles: `owner` | `member`. Stored in `project_members.role`.
- **owner** — can delete project, invite, remove members, everything member can.
- **member** — CRUD tasks/sections/comments inside the project, cannot delete the project or manage membership.
- On project create — creator auto-added as `owner` row in `project_members`.
- `get_project/get_task/get_section` — access granted if requester is a **member** (any role) of the relevant project.
- `delete_project` + member-management — `owner` only.
- `list_projects` — projects where user is owner OR member.
- Personal views (`list_today`, `list_upcoming`, `list_trash`, `list_completed*`) — stay personal: `Task.user_id == me OR Task.assigned_to == me`. NOT all tasks of all shared projects (avoids noise).
- Project view (`list_tasks(project_id=...)`) — all tasks of the project, for any member.

---

## File Structure

```
CREATE:
app/projects/membership.py            δ2: ProjectMember/ProjectInvitation service layer
app/projects/invitations.py           δ4: invite/accept/revoke logic
app/templates/invite.html             δ5: accept-invitation page
tests/test_project_members.py         δ2
tests/test_project_permissions.py     δ3
tests/test_project_invitations.py     δ4
tests/test_task_assignee.py           δ6
alembic/versions/0030_team_collab.py  δ1

MODIFY:
app/projects/models.py                δ1: + ProjectMember, ProjectInvitation models
app/tasks/models.py                   δ1: + assigned_to column
tests/conftest.py                     δ1: + second_user / second_logged_in_client fixtures
app/projects/service.py               δ3: get_project + list_projects → membership-aware; create_project auto-owner; delete_project owner-only
app/tasks/service.py                  δ3: get_task → membership-aware; create_task project-membership check
app/sections/service.py               δ3: get_section → via project membership
app/auth/email.py                     δ4: + send_invitation_email
app/projects/router.py                δ5: + members + invites endpoints
app/main.py                           δ5: mount invite page router
app/views/router.py                   δ5: GET/POST /invite/{token}
app/tasks/router.py + miniapp/router  δ6: assigned_to in PATCH + task dict
app/templates/app/project.html        δ7: «Поделиться» modal + members
app/templates/_partials/task_detail.html + miniapp task_sheet.html  δ7: assignee selector
```

---

## Task 1: DB schema + migration + test fixtures

**Files:** `app/projects/models.py`, `app/tasks/models.py`, `alembic/versions/0030_team_collab.py`, `tests/conftest.py`

- [ ] **Step 1: Add models to `app/projects/models.py`**

After the `Project` class, add:

```python
class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        Index("uq_project_member", "project_id", "user_id", unique=True),
        Index("ix_project_members_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ProjectInvitation(Base):
    __tablename__ = "project_invitations"
    __table_args__ = (
        Index("ix_project_invitations_token", "token", unique=True),
        Index("ix_project_invitations_email", "invitee_email"),
        Index("ix_project_invitations_project", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    inviter_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
```

Check the file head — confirm `_utcnow`, `UUID`, `uuid4`, `ForeignKey`, `Index`, `String`, `DateTime`, `Mapped`, `mapped_column`, `datetime` are imported. Add any missing import to the existing import block.

- [ ] **Step 2: Add `assigned_to` to `app/tasks/models.py`**

In the `Task` class, after `section_id`:
```python
assigned_to: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", ondelete="SET NULL"), nullable=True
)
```

- [ ] **Step 3: Create migration `alembic/versions/0030_team_collab.py`**

```python
"""team collaboration — project_members, project_invitations, tasks.assigned_to

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_project_member", "project_members", ["project_id", "user_id"], unique=True
    )
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    op.create_table(
        "project_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inviter_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invitee_email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_invitations_token", "project_invitations", ["token"], unique=True
    )
    op.create_index(
        "ix_project_invitations_email", "project_invitations", ["invitee_email"]
    )
    op.create_index(
        "ix_project_invitations_project", "project_invitations", ["project_id"]
    )

    op.add_column(
        "tasks",
        sa.Column(
            "assigned_to",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill: every existing project → owner-row in project_members
    op.execute(
        """
        INSERT INTO project_members (id, project_id, user_id, role, joined_at)
        SELECT gen_random_uuid(), p.id, p.user_id, 'owner', now()
        FROM projects p
        """
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Team-collab schema is forward-only; restore from backup if needed."
    )
```

**Note:** `gen_random_uuid()` is a Postgres 13+ builtin (pgcrypto-free since PG13). Confirm prod PG version is 13+ — recon said PG16, so it's fine.

- [ ] **Step 4: Add second-user fixtures to `tests/conftest.py`**

Read the existing `logged_in_client` fixture to copy its exact pattern (user creation + force-verify + login POST). Add:

```python
@pytest.fixture
async def second_user(db_session: AsyncSession) -> "User":
    """A second distinct user — for permission / sharing tests."""
    from datetime import UTC, datetime

    from app.auth.models import User
    from app.auth.schemas import RegisterIn
    from app.auth.service import register_user

    user = await register_user(
        db_session, RegisterIn(email="second@example.com", password="strongpass456")
    )
    user.email_verified_at = datetime.now(UTC)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def second_logged_in_client(
    db_session: AsyncSession, second_user: "User"
) -> "AsyncIterator[AsyncClient]":
    """An AsyncClient logged in as second_user. Separate cookie jar from logged_in_client."""
    from httpx import ASGITransport, AsyncClient

    from app.db import get_session
    from app.main import app

    async def _override() -> "AsyncIterator[AsyncSession]":
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post(
            "/auth/login",
            data={"email": "second@example.com", "password": "strongpass456"},
        )
        yield c
    app.dependency_overrides.clear()
```

**IMPORTANT:** match the EXACT mechanism the existing `logged_in_client` uses (it may use a different login path/payload, a different transport setup, or a helper). Read it first and mirror it precisely — only changing the email/password. If `logged_in_client` uses form-data vs json, match that.

- [ ] **Step 5: Add a model-sanity test**

In `tests/test_project_members.py` (new file):
```python
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
```

- [ ] **Step 6: mypy + pre-commit + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
git add app/projects/models.py app/tasks/models.py alembic/versions/0030_team_collab.py tests/conftest.py tests/test_project_members.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(δ): схема team-collab — project_members + invitations + assigned_to

ProjectMember (project_id, user_id, role owner|member), ProjectInvitation
(token, status, expires_at), tasks.assigned_to FK. Миграция 0030 создаёт
2 таблицы + колонку + backfill: каждый существующий проект получает
owner-row в project_members. conftest: second_user / second_logged_in_client
фикстуры для permission-тестов.
EOF
)"
```
Do NOT push (push is δ8).

---

## Task 2: Membership service layer

**Files:** Create `app/projects/membership.py`, `tests/test_project_members.py` (extend)

- [ ] **Step 1: Create `app/projects/membership.py`**

```python
"""Service layer for project membership — who can access a shared project."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import ProjectMember


async def is_member(session: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    """True if user has any role in the project."""
    row = await session.execute(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return row.first() is not None


async def get_role(session: AsyncSession, project_id: UUID, user_id: UUID) -> str | None:
    """'owner' | 'member' | None."""
    row = await session.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return row.scalar_one_or_none()


async def is_owner(session: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    return (await get_role(session, project_id, user_id)) == "owner"


async def list_members(session: AsyncSession, project_id: UUID) -> list[ProjectMember]:
    rows = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    return list(rows.scalars().all())


async def add_member(
    session: AsyncSession, project_id: UUID, user_id: UUID, role: str = "member"
) -> ProjectMember:
    """Idempotent — if already a member, returns existing row (role unchanged)."""
    existing = await session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(session: AsyncSession, project_id: UUID, user_id: UUID) -> None:
    """Remove a member. Caller must ensure not removing the last owner."""
    await session.execute(
        delete(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    await session.commit()


async def member_project_ids(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """All project ids the user is a member of (any role)."""
    rows = await session.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    )
    return list(rows.scalars().all())
```

- [ ] **Step 2: Extend `tests/test_project_members.py`**

Add tests using `db_session`, `logged_in_client` (to get user1), `second_user`:
```python
async def test_add_member_idempotent(db_session, logged_in_client, second_user) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.membership import add_member, is_member, list_members
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    project = await create_project(db_session, user1.id, name="Shared", color="violet")
    await db_session.commit()

    # creator should already be owner (create_project auto-adds — see δ3),
    # but if δ3 not applied yet, add explicitly:
    await add_member(db_session, project.id, second_user.id, role="member")
    await add_member(db_session, project.id, second_user.id, role="member")  # idempotent
    members = await list_members(db_session, project.id)
    user2_rows = [m for m in members if m.user_id == second_user.id]
    assert len(user2_rows) == 1
    assert await is_member(db_session, project.id, second_user.id) is True


async def test_remove_member(db_session, logged_in_client, second_user) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.membership import add_member, is_member, remove_member
    from app.projects.service import create_project

    user1 = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    project = await create_project(db_session, user1.id, name="P", color="violet")
    await db_session.commit()
    await add_member(db_session, project.id, second_user.id)
    await remove_member(db_session, project.id, second_user.id)
    assert await is_member(db_session, project.id, second_user.id) is False
```

**IMPORTANT:** `create_project` signature — verify it from `app/projects/service.py` (recon said `create_project(session, user_id, *, name, color)`). Match exactly.

- [ ] **Step 3: pre-commit + pytest + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_project_members.py 2>&1 | tail -10
git add app/projects/membership.py tests/test_project_members.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "feat(δ): membership service — is_member/is_owner/add/remove/list"
```
ConnectionRefusedError accepted if local Postgres down — but if PG is up, these tests SHOULD pass. Do NOT push.

---

## Task 3: Permission integration in core services (HIGHEST RISK)

**Files:** `app/projects/service.py`, `app/tasks/service.py`, `app/sections/service.py`, `tests/test_project_permissions.py`

The gate goes into 3 functions + `list_projects` + `create_project`. This is the security-critical task.

- [ ] **Step 1: `create_project` — auto-add owner row**

In `app/projects/service.py`, in `create_project`, after the project is committed/refreshed, add an owner membership row:
```python
from app.projects.membership import add_member  # add to imports
# ... after `await session.refresh(project)`:
await add_member(session, project.id, user_id, role="owner")
```
Check `add_member` commits internally — if `create_project` already committed the project, calling `add_member` (which commits again) is fine.

- [ ] **Step 2: `get_project` — membership-aware**

Current (recon lines 52-55):
```python
async def get_project(session, user_id, project_id):
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user_id:
        raise ProjectNotFound(...)
    return project
```
Change the ownership check to membership check:
```python
async def get_project(session, user_id, project_id):
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFound(...)
    from app.projects.membership import is_member
    if not await is_member(session, project_id, user_id):
        raise ProjectNotFound(...)
    return project
```
**Verify the actual current code first** — match the exact exception class + message it raises.

- [ ] **Step 3: `list_projects` + `list_archived_projects` — member projects**

Current: `WHERE Project.user_id == user_id`. Change to: projects where user is a member.
```python
from app.projects.membership import member_project_ids
# in list_projects:
ids = await member_project_ids(session, user_id)
stmt = select(Project).where(Project.id.in_(ids))
# ... keep the rest (include_archived filter, order_by) as-is
```
Apply the same to `list_archived_projects`. **Edge case:** if `ids` is empty, `Project.id.in_([])` is valid SQL (returns nothing) — fine.

- [ ] **Step 4: `delete_project` — owner only**

In `delete_project`, after `get_project` (which now allows any member), add an owner check:
```python
from app.projects.membership import is_owner
if not await is_owner(session, project_id, user_id):
    raise ProjectNotFound(...)  # or a dedicated 403 — but 404 keeps it consistent + leaks nothing
```
Use the same `ProjectNotFound` for non-owner delete attempts (don't leak that the project exists).

- [ ] **Step 5: `get_task` — membership-aware**

Current (recon lines 38-41): `if task.user_id != user_id: raise TaskNotFound`. Change:
```python
async def get_task(session, user_id, task_id):
    task = await session.get(Task, task_id)
    if task is None:
        raise TaskNotFound(...)
    from app.projects.membership import is_member
    if not await is_member(session, task.project_id, user_id):
        raise TaskNotFound(...)
    return task
```

- [ ] **Step 6: `create_task` — project membership check**

`create_task` currently calls `get_project(session, user_id, project_id)` to verify project ownership — now that `get_project` is membership-aware, this automatically becomes a membership check. **No change needed** beyond confirming it still calls `get_project`. Same for the `parent_task_id` check via `get_task`. Verify these calls exist and leave them.

- [ ] **Step 7: `get_section` — via project membership**

Current: `if section.user_id != user_id: raise SectionNotFound`. Change to check membership of `section.project_id`:
```python
async def get_section(session, user_id, section_id):
    section = await session.get(Section, section_id)
    if section is None:
        raise SectionNotFound(...)
    from app.projects.membership import is_member
    if not await is_member(session, section.project_id, user_id):
        raise SectionNotFound(...)
    return section
```
`list_sections` already calls `get_project` first — automatically membership-aware now. `create_section` calls `get_project` — same. Verify and leave.

- [ ] **Step 8: Personal views stay personal — verify NO change needed**

`list_today`, `list_upcoming`, `list_trash`, `list_completed*` filter `WHERE Task.user_id == user_id`. These should STAY as-is — personal views show only my own tasks. (A future enhancement could add `OR Task.assigned_to == user_id`, but δ keeps it simple: personal views = my tasks only. Project view shows everything.) **Do not modify these functions.** Just confirm `list_tasks(project_id=...)` (the project-view query) — recon said it filters `Task.user_id`; CHANGE it: when `project_id` is given, filter by `project_id` only (membership already verified by the router calling `get_project` first) — drop the `user_id` filter for the project-scoped case so members see each other's tasks. Read `list_tasks` carefully — if it's used by both project-view and personal contexts, only relax the `user_id` filter in the `project_id is not None` branch.

- [ ] **Step 9: Write `tests/test_project_permissions.py`**

```python
"""Phase δ — permission boundary tests: non-members get 404."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_project(db_session: AsyncSession, email: str, name: str):
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
    # second user is NOT a member
    r = await second_logged_in_client.patch(
        f"/api/projects/{project.id}", json={"name": "hacked"}
    )
    assert r.status_code == 404


async def test_member_can_access_after_add(
    db_session: AsyncSession, logged_in_client: AsyncClient,
    second_logged_in_client: AsyncClient, second_user,
) -> None:
    from app.projects.membership import add_member

    _, project = await _make_project(db_session, "logged-in@example.com", "Shared")
    await add_member(db_session, project.id, second_user.id, role="member")
    r = await second_logged_in_client.patch(
        f"/api/projects/{project.id}", json={"name": "renamed by member"}
    )
    assert r.status_code == 200


async def test_member_cannot_delete_project(
    db_session: AsyncSession, logged_in_client: AsyncClient,
    second_logged_in_client: AsyncClient, second_user,
) -> None:
    from app.projects.membership import add_member

    _, project = await _make_project(db_session, "logged-in@example.com", "Shared2")
    await add_member(db_session, project.id, second_user.id, role="member")
    r = await second_logged_in_client.delete(f"/api/projects/{project.id}")
    assert r.status_code == 404  # member can't delete — owner-only


async def test_non_member_cannot_access_task(
    db_session: AsyncSession, logged_in_client: AsyncClient, second_logged_in_client: AsyncClient
) -> None:
    from app.tasks.service import create_task

    user, project = await _make_project(db_session, "logged-in@example.com", "P")
    task = await create_task(db_session, user.id, title="secret", project_id=project.id)
    await db_session.commit()
    r = await second_logged_in_client.patch(f"/api/tasks/{task.id}", json={"title": "x"})
    assert r.status_code == 404
```

**IMPORTANT:** verify endpoint paths + payloads against the actual routers (recon listed them). `create_task` signature — recon said `create_task(session, user_id, *, title, project_id, ...)`. Match exactly.

- [ ] **Step 10: pre-commit + pytest + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_project_permissions.py tests/test_projects/ tests/test_tasks/ tests/test_sections.py 2>&1 | tail -20
```
mypy --strict must pass. The existing project/task/section tests MUST still pass (they use a single user who is auto-owner — `create_project` auto-adds owner, so `get_project` membership check passes for them). If existing tests break — investigate: likely a test creates a Project directly via `session.add(Project(...))` bypassing `create_project`, so no owner row exists. Fix such tests to use `create_project` OR add an explicit `add_member(..., role="owner")`.

```bash
git add app/projects/service.py app/tasks/service.py app/sections/service.py tests/
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(δ): permission-слой — get_project/get_task/get_section через membership

get_project/get_task/get_section теперь проверяют is_member вместо
user_id == owner. list_projects возвращает проекты где юзер участник.
create_project авто-добавляет owner-row. delete_project — owner-only.
list_tasks(project_id) показывает задачи всех участников проекта.
Личные views (Today/Upcoming/Trash) остаются личными — только свои задачи.
EOF
)"
```
Do NOT push.

## Context for Task 3

This is the highest-risk task. The whole security model hinges on it. If existing tests break in unexpected ways or the `list_tasks` dual-use is too tangled — STOP and report DONE_WITH_CONCERNS. A broken permission layer is worse than a delayed one.

---

## Task 4: Invitations service + email

**Files:** Create `app/projects/invitations.py`, modify `app/auth/email.py`, create `tests/test_project_invitations.py`

- [ ] **Step 1: `send_invitation_email` in `app/auth/email.py`**

Read the existing `send_verification_email` + `_render_html` + `_render_text` to copy the exact structure (EmailMessage build, aiosmtplib.send call, settings usage). Add:

```python
async def send_invitation_email(
    *, to: str, invite_url: str, project_name: str, inviter_email: str
) -> None:
    """Send a project invitation email. Mirrors send_verification_email."""
    settings = get_settings()
    subject = f"Тебя пригласили в проект «{project_name}» на Doday"
    text = (
        f"Привет!\n\n"
        f"{inviter_email} приглашает тебя в проект «{project_name}» на Doday — "
        f"это совместный to-do list.\n\n"
        f"Принять приглашение: {invite_url}\n"
        f"(ссылка действует 7 дней)\n\n"
        f"Если ты не знаешь этого человека — просто проигнорируй письмо."
    )
    html = (
        f"<p>Привет!</p>"
        f"<p><b>{inviter_email}</b> приглашает тебя в проект "
        f"«<b>{project_name}</b>» на Doday — это совместный to-do list.</p>"
        f'<p><a href="{invite_url}">Принять приглашение</a> (ссылка действует 7 дней)</p>'
        f"<p style='color:#888;font-size:13px'>Если ты не знаешь этого человека — "
        f"просто проигнорируй письмо.</p>"
    )
    # ... build EmailMessage + aiosmtplib.send EXACTLY as send_verification_email does
```
Match the exact send mechanism (connection params, start_tls handling) from `send_verification_email`.

- [ ] **Step 2: Create `app/projects/invitations.py`**

```python
"""Project invitation logic — create / accept / revoke."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project, ProjectInvitation
from app.projects.membership import add_member, is_member, is_owner

INVITE_TTL_DAYS = 7


class InvitationError(Exception):
    """Base for invitation problems."""


async def create_invitation(
    session: AsyncSession,
    *,
    project_id: UUID,
    inviter_id: UUID,
    invitee_email: str,
) -> ProjectInvitation:
    """Create a pending invitation. Raises InvitationError on bad input."""
    invitee_email = invitee_email.lower().strip()
    if not await is_owner(session, project_id, inviter_id):
        raise InvitationError("Только владелец проекта может приглашать")

    # inviter inviting themselves?
    from app.auth.service import get_user_by_email

    existing_user = await get_user_by_email(session, invitee_email)
    if existing_user is not None and await is_member(session, project_id, existing_user.id):
        raise InvitationError("Этот юзер уже в проекте")

    # revoke any prior pending invite for the same email+project
    prior = await session.execute(
        select(ProjectInvitation).where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.invitee_email == invitee_email,
            ProjectInvitation.status == "pending",
        )
    )
    for inv in prior.scalars().all():
        inv.status = "revoked"

    invitation = ProjectInvitation(
        project_id=project_id,
        inviter_id=inviter_id,
        invitee_email=invitee_email,
        token=secrets.token_urlsafe(32),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def accept_invitation(
    session: AsyncSession, *, token: str, user_id: UUID, user_email: str
) -> Project:
    """Accept an invitation. Returns the project. Raises InvitationError."""
    row = await session.execute(
        select(ProjectInvitation).where(ProjectInvitation.token == token)
    )
    inv = row.scalar_one_or_none()
    if inv is None or inv.status != "pending":
        raise InvitationError("Приглашение не найдено или уже использовано")
    if inv.expires_at < datetime.now(UTC):
        inv.status = "revoked"
        await session.commit()
        raise InvitationError("Срок приглашения истёк")
    if inv.invitee_email != user_email.lower().strip():
        raise InvitationError("Приглашение выписано на другой email")

    await add_member(session, inv.project_id, user_id, role="member")
    inv.status = "accepted"
    inv.accepted_at = datetime.now(UTC)
    await session.commit()

    project = await session.get(Project, inv.project_id)
    assert project is not None
    return project


async def revoke_invitation(
    session: AsyncSession, *, invitation_id: UUID, requester_id: UUID
) -> None:
    row = await session.execute(
        select(ProjectInvitation).where(ProjectInvitation.id == invitation_id)
    )
    inv = row.scalar_one_or_none()
    if inv is None:
        raise InvitationError("Приглашение не найдено")
    if not await is_owner(session, inv.project_id, requester_id):
        raise InvitationError("Только владелец может отзывать приглашения")
    inv.status = "revoked"
    await session.commit()


async def list_pending(
    session: AsyncSession, project_id: UUID
) -> list[ProjectInvitation]:
    rows = await session.execute(
        select(ProjectInvitation)
        .where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.status == "pending",
        )
        .order_by(ProjectInvitation.created_at.desc())
    )
    return list(rows.scalars().all())
```

- [ ] **Step 3: Write `tests/test_project_invitations.py`**

Tests for: create (owner only), accept (valid token → membership), accept wrong-email rejected, accept expired rejected, revoke. Use `db_session`, `logged_in_client`, `second_user`. Follow the pattern from `test_project_permissions.py`. Include at minimum:
- `test_create_invitation_by_owner`
- `test_create_invitation_non_owner_rejected`
- `test_accept_invitation_adds_member`
- `test_accept_wrong_email_rejected`
- `test_accept_expired_rejected` (manually set `expires_at` to the past)
- `test_revoke_invitation`

Write actual test bodies — no placeholders. Mirror `test_project_permissions.py` structure.

- [ ] **Step 4: pre-commit + pytest + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_project_invitations.py 2>&1 | tail -10
git add app/projects/invitations.py app/auth/email.py tests/test_project_invitations.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(δ): invitations — create/accept/revoke + email-приглашение

create_invitation (owner-only, token 7 дней, ревок прежних pending),
accept_invitation (валидация token/expiry/email → add_member),
revoke_invitation, list_pending. send_invitation_email через
aiosmtplib — тот же механизм что verification email.
EOF
)"
```
Do NOT push.

---

## Task 5: Invitations API + accept page

**Files:** `app/projects/router.py`, `app/views/router.py`, `app/main.py`, create `app/templates/invite.html`

- [ ] **Step 1: Members + invites endpoints in `app/projects/router.py`**

Add (match the file's existing endpoint style — `RequiredUser`, `DbSession`, error→HTTPException mapping):

```python
GET    /api/projects/{project_id}/members          → list members (member access)
POST   /api/projects/{project_id}/invites          → create invitation (owner-only) + send email
GET    /api/projects/{project_id}/invites          → list pending (owner-only)
DELETE /api/invites/{invitation_id}                → revoke (owner-only)
DELETE /api/projects/{project_id}/members/{user_id} → remove member (owner-only)
```

For `POST .../invites` — call `create_invitation`, build the invite URL (`settings.app_base_url + "/invite/" + token`), call `send_invitation_email`. Wrap `InvitationError` → `HTTPException(400, detail=str(e))`.

For member-list response include the user's email (join `ProjectMember` → `User`). Define a small Pydantic `MemberOut {user_id, email, role, joined_at}` and `InvitationOut {id, invitee_email, status, expires_at}` in the router or `app/projects/schemas.py` if that file exists.

`DELETE .../members/{user_id}` — owner-only; refuse to remove the last owner (if `user_id` is the only owner, return 400).

- [ ] **Step 2: `GET/POST /invite/{token}` in `app/views/router.py`**

```python
GET  /invite/{token}  — render invite.html. If not logged in → still render the page
                        with a "войти/зарегистрироваться чтобы принять" prompt
                        (pass next=/invite/{token}). If logged in → show "принять" button.
POST /invite/{token}  — RequiredUser. Call accept_invitation(session, token=token,
                        user_id=user.id, user_email=user.email). On success →
                        RedirectResponse to /app/projects (303). On InvitationError →
                        re-render invite.html with the error message.
```

- [ ] **Step 3: Create `app/templates/invite.html`**

Extends the public base (check what `login.html` / `register.html` extend — match it). Shows:
- Project name + inviter email ("Вас пригласил X в проект Y")
- If `current_user`: a POST form with "Принять приглашение" button
- If not `current_user`: "Войдите или зарегистрируйтесь, чтобы принять" with links to `/auth/login?next=/invite/{token}` and `/auth/register?next=/invite/{token}`
- If `error` in context: red error banner

- [ ] **Step 4: Mount the route**

`/invite/{token}` likely lives in `app/views/router.py` which is already mounted — confirm. If a new router is created, add `app.include_router(...)` to `app/main.py`.

- [ ] **Step 5: Tests** — extend `tests/test_project_invitations.py` with endpoint-level tests:
- `test_post_invite_endpoint_owner` — POST `/api/projects/{id}/invites` as owner → 200/201
- `test_post_invite_endpoint_non_owner_403` — as non-member → 404 (get_project gate) or 400
- `test_get_invite_page_renders` — GET `/invite/{token}` → 200, project name in HTML
- `test_accept_via_post_endpoint` — second user POSTs `/invite/{token}` → 303, then they're a member

- [ ] **Step 6: pre-commit + pytest + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_project_invitations.py 2>&1 | tail -10
git add app/projects/router.py app/views/router.py app/main.py app/templates/invite.html app/projects/schemas.py tests/
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "feat(δ): API членов + инвайтов + страница /invite/{token}"
```
Do NOT push.

---

## Task 6: Assignee field

**Files:** `app/tasks/router.py`, `app/tasks/service.py`, `app/miniapp/router.py`, `tests/test_task_assignee.py`

- [ ] **Step 1: `update_task` accepts `assigned_to`**

In `app/tasks/service.py::update_task` — if `assigned_to` is in kwargs:
- `None` → clear assignment
- a UUID → verify that user is a member of `task.project_id` (use `is_member`); if not a member, raise a validation error / ignore. Recommended: raise `TaskNotFound`-style or a `ValueError` mapped to 400.

- [ ] **Step 2: `assigned_to` in task serialization**

Find `_task_to_dict` (recon mentioned it in miniapp/router) and the `TaskOut` schema (`app/tasks/schemas.py`). Add `assigned_to: UUID | None`. Also add `assignee_email: str | None` if convenient (join) — optional, only if low-effort; otherwise just the UUID.

- [ ] **Step 3: PATCH endpoint accepts it**

`PATCH /api/tasks/{task_id}` — the `TaskPatchIn` schema (`app/tasks/schemas.py` or wherever) gets `assigned_to: UUID | None = None`. Wire it through to `update_task`. Same for miniapp's `TaskPatchIn` if it has a separate one.

- [ ] **Step 4: Tests `tests/test_task_assignee.py`**

- `test_assign_task_to_member` — owner assigns task to a member → 200, `assigned_to` set
- `test_assign_to_non_member_rejected` — assign to a non-member → 400 (or assignment ignored)
- `test_clear_assignee` — PATCH `assigned_to: null` → cleared

- [ ] **Step 5: pre-commit + pytest + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_task_assignee.py 2>&1 | tail -10
git add app/tasks/ app/miniapp/router.py tests/test_task_assignee.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "feat(δ): assignee — tasks.assigned_to в PATCH + сериализации, member-валидация"
```
Do NOT push.

---

## Task 7: UI — «Поделиться» modal + members + assignee selector

**Files:** `app/templates/app/project.html`, `app/templates/_partials/task_detail.html`, `app/templates/miniapp/_partials/task_sheet.html`

- [ ] **Step 1: «Поделиться» button + modal on `app/templates/app/project.html`**

Read the file. Add a «Поделиться» button near the project header. Clicking opens an Alpine modal:
- Email input + «Пригласить» button → `POST /api/projects/{id}/invites`
- «Уже в проекте» list — fetches `GET /api/projects/{id}/members`, shows email + role; owner sees a remove (🗑) button per member (not for themselves / not last owner)
- «Ожидают» list — fetches `GET /api/projects/{id}/invites`, shows pending emails + revoke button
- All via Alpine `x-data` + `fetch`. Match the Alpine patterns already used elsewhere in the app.

The «Поделиться» button + modal should only render for the project **owner** — pass an `is_owner` flag from the project-view handler context (`app/views/router.py` — the handler rendering `project.html`). Non-owners see members list read-only or nothing.

- [ ] **Step 2: Assignee selector — web `task_detail.html`**

Add an «Назначить» row: a `<select>` (or Alpine dropdown) listing project members (fetched from `/api/projects/{project_id}/members`), PATCHes `assigned_to` on change. Show current assignee. Only show the selector if the project has > 1 member (solo projects don't need it).

- [ ] **Step 3: Assignee selector — Mini App `task_sheet.html`**

Same idea in the bottom-sheet — a member picker that PATCHes `assigned_to`. Match the existing picker style (like the project/labels pickers in the sheet).

- [ ] **Step 4: jinja-linter + pre-commit**

```bash
uv run python scripts/lint_templates.py 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -10
```

- [ ] **Step 5: commit**

```bash
git add app/templates/
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "feat(δ): UI — «Поделиться» modal, список участников, выбор исполнителя"
```
Do NOT push.

## Context for Task 7

UI task — match existing Alpine/Tailwind patterns. If the project.html structure is hard to safely extend — do the modal as a separate `_partials/share_modal.html` include. Report DONE_WITH_CONCERNS if assignee-selector wiring into task_sheet is too tangled — a backend-complete δ with partial UI is acceptable; the controller can follow up.

---

## Task 8: Push + deploy + smoke + PROGRESS

- [ ] **Step 1: Sanity** — `git log --oneline -10`, confirm δ1-δ7 commits.
- [ ] **Step 2: Push** via TOKEN from `.env` to `github.com/SwairIt/doday` master.
- [ ] **Step 3: Wait deploy** — `until curl -fsS https://getdoday.ru/health | grep ok`, then SSH-poll prod HEAD == local HEAD (max 5 min).
- [ ] **Step 4: Verify migration 0030** — check `deploy-poll.log` for `Running upgrade 0029 -> 0030`. Confirm no errors.
- [ ] **Step 5: Smoke 23/23** — `uv run python scripts/smoke_test.py https://getdoday.ru`.
- [ ] **Step 6: Verify prod tables** — SSH + psql: confirm `project_members` + `project_invitations` exist, `tasks.assigned_to` column exists, and `project_members` has backfilled owner-rows (count should equal `projects` count).
- [ ] **Step 7: Update PROGRESS.md** — prepend a «2026-05-14 — Phase δ: team collaboration завершён» entry. Commit + push.
- [ ] **Step 8: Report** — push output, prod HEAD match, migration confirmed, smoke result, table verification, concerns.

---

## Self-Review (выполнено)

**Spec coverage:** project_members + project_invitations + assigned_to (δ1), membership service (δ2), permission integration (δ3), invitations + email (δ4), API + accept page (δ5), assignee (δ6), UI (δ7), deploy (δ8). All spec items mapped.

**Placeholder scan:** no TBD. Models/migration/service code given verbatim. Tasks 3/5/7 contain "verify against actual code / match existing pattern" guidance because exact signatures depend on runtime — implementer reads the file first (recon gave line numbers as anchors).

**Type/name consistency:** `is_member`/`is_owner`/`add_member`/`member_project_ids` — consistent between membership.py definition and its callers in service.py + invitations.py. `ProjectInvitation.status` values `pending|accepted|revoked` — consistent across create/accept/revoke/list_pending. `0030` revision, `down_revision=0029` — matches recon's latest.

**Scope check:** 8 tasks, sequential. δ3 is the security-critical one — flagged HIGH RISK with explicit "stop if tests break unexpectedly" guidance. δ1 must run first (models + fixtures). δ3 depends on δ2 (membership service). δ5 depends on δ4. δ6 independent-ish but needs δ1's column. δ7 needs δ5's endpoints.

**Risk:** δ3 changing `get_task`/`get_project`/`get_section` affects EVERY existing test. Mitigation: `create_project` auto-adds owner row, so single-user tests still pass. The plan explicitly tells the implementer to fix tests that bypass `create_project`.

---

## Execution Handoff

Continue with **subagent-driven-development**. δ3 implementer should use a capable model (sonnet) — it's the security-critical task.
