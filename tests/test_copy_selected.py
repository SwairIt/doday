"""Bulk "copy selected to clipboard" — the task rows expose an exact-case title
attribute and the bulk bar wires the copy action. Copy itself is Playwright-verified."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tasks.service import create_task


async def _owner(db_session: AsyncSession) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()


async def test_task_row_has_exact_title_attr(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _owner(db_session)
    await create_task(db_session, user.id, title="Купить Молоко", due_at=datetime.now(UTC))

    body = (await logged_in_client.get("/doday/app/today")).text
    # Exact-case title (not the lowercased data-title) is available for copying.
    assert 'data-title-text="Купить Молоко"' in body


async def test_bulk_bar_has_copy_action(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "copySelected()" in body
    assert "navigator.clipboard" in body
    assert "Скопировать выделенные" in body
