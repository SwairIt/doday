"""Lessio cabinet: /lessio/app/clients — list + detail."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioClient, LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _setup_with_bookings(
    client: AsyncClient, db_session: AsyncSession, *, tg_id: int
) -> tuple[str, LessioClient]:
    slug = f"cli_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"cl{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    service = (
        (
            await db_session.execute(
                select(LessioService).where(LessioService.tutor_id == profile.id)
            )
        )
        .scalars()
        .first()
    )
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        await create_booking(
            db_session,
            tutor=profile,
            service=service,
            slot=datetime(2026, 6, 8, 14, 0, tzinfo=UTC),
            client_email="alice@e.com",
            client_full_name="Alice Wonder",
            client_phone="+79991111111",
        )
        await db_session.commit()
    alice = (
        await db_session.execute(select(LessioClient).where(LessioClient.email == "alice@e.com"))
    ).scalar_one()
    return slug, alice


async def test_clients_list_renders(client: AsyncClient, db_session: AsyncSession) -> None:
    await _setup_with_bookings(client, db_session, tg_id=73000001)
    resp = await client.get("/lessio/app/clients")
    assert resp.status_code == 200
    assert "Alice Wonder" in resp.text
    assert "alice@e.com" in resp.text


async def test_clients_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    # Tutor без booking'ов = пустой clients-список
    await client.post(
        "/lessio/auth/register",
        data={"email": "cl73000002@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "cli_73000002", "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    resp = await client.get("/lessio/app/clients")
    assert resp.status_code == 200
    assert "пока нет" in resp.text.lower() or "клиент" in resp.text.lower()


async def test_client_detail_shows_bookings(client: AsyncClient, db_session: AsyncSession) -> None:
    _, alice = await _setup_with_bookings(client, db_session, tg_id=73000003)
    resp = await client.get(f"/lessio/app/clients/{alice.id}")
    assert resp.status_code == 200
    assert "Alice Wonder" in resp.text
    # Должна показаться созданная встреча
    assert "08.06.2026" in resp.text or "14:00" in resp.text
