"""The project page shows a «Лейбл» filter chip when its tasks carry labels,
and omits it otherwise. The filtering itself is Playwright-verified."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.labels.service import attach_label, create_label
from app.projects.service import create_project
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_label_filter_present_with_labeled_task(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="С лейблами")
    task = await create_task(db_session, user.id, title="помеченная", project_id=project.id)
    label = await create_label(db_session, user.id, name="work")
    await attach_label(db_session, user.id, task.id, label.id)
    # Capture ids/slug before expiring — accessing them after expire would
    # trigger a lazy reload outside the async greenlet.
    label_id = label.id
    slug = project.slug
    # The shared test session caches the task's (empty) labels collection from
    # create time; the raw association insert doesn't refresh it. In production
    # each request uses a fresh session. Expire so the GET reloads labels.
    db_session.expire_all()

    body = (await logged_in_client.get(f"/app/projects/{slug}")).text
    # Row carries the label id, the chip is rendered, the label appears as an option.
    assert f'data-labels="{label_id}"' in body
    assert "setLabelFilter('all')" in body
    assert ">work</span>" in body


async def test_label_filter_absent_without_labels(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    project = await create_project(db_session, user.id, name="Без лейблов")
    await create_task(db_session, user.id, title="без метки", project_id=project.id)

    body = (await logged_in_client.get(f"/app/projects/{project.slug}")).text
    assert "без метки" in body
    # No labels on any task → the filter chip is not rendered.
    assert "setLabelFilter('all')" not in body
