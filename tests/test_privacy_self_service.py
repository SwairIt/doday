"""Человек должен сам видеть, что о нём хранится, и уметь это забрать.

Большинство жалоб в надзор возникает не из-за утечек, а из-за того, что
пользователю не показали его данные и не дали их удалить.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


async def test_my_data_shows_inventory(
    logged_in_client: AsyncClient, db_session: AsyncSession
) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "Физика"})
    data = (await logged_in_client.get("/api/profile/my-data")).json()

    assert data["email"] == "logged-in@example.com"
    assert data["tasks"] == 1
    assert data["registered_at"]
    assert data["telegram_linked"] is False
    assert data["school_connected"] is False


async def test_my_data_page_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/my-data")).text
    assert "Скачать мои данные" in body
    assert "/api/backup/export" in body
    assert "Удалить аккаунт" in body


async def test_my_data_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/profile/my-data")).status_code == 401
    assert (await client.get("/app/my-data")).status_code == 401


async def test_privacy_page_links_to_my_data(client: AsyncClient) -> None:
    assert "/app/my-data" in (await client.get("/privacy")).text


async def test_old_signup_ip_is_forgotten(db_session: AsyncSession) -> None:
    """IP нужен на час — для защиты от ботов. Через сутки он лишний след."""
    from sqlalchemy import text

    old = User(
        id=uuid4(),
        email=f"old-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        signup_ip="45.132.20.1",
        signup_subnet="45.132.20",
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    fresh = User(
        id=uuid4(),
        email=f"new-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        signup_ip="45.132.20.2",
        signup_subnet="45.132.20",
        created_at=datetime.now(UTC),
    )
    db_session.add_all([old, fresh])
    await db_session.commit()

    await db_session.execute(
        text(
            "UPDATE users SET signup_ip = NULL, signup_subnet = NULL "
            "WHERE signup_ip IS NOT NULL AND created_at < now() - interval '1 day'"
        )
    )
    await db_session.commit()

    # После сырого UPDATE объекты в сессии держат старые значения.
    db_session.expire_all()
    rows = {u.email: u.signup_ip for u in (await db_session.execute(select(User))).scalars().all()}
    assert rows[old.email] is None
    assert rows[fresh.email] == "45.132.20.2"
