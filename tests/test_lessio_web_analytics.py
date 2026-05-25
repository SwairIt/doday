"""Yandex.Metrika tracking + Sentry tutor-tag on Lessio public/private pages."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


def _setup_metrika(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ya_metrika_id", "99999999")


async def test_lessio_landing_emits_metrika_when_configured(
    client: AsyncClient, monkeypatch
) -> None:
    _setup_metrika(monkeypatch)
    resp = await client.get("/lessio")
    body = resp.text
    assert "mc.yandex.ru/metrika/tag.js" in body
    assert "99999999" in body


async def test_public_profile_emits_metrika(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _setup_metrika(monkeypatch)
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=92000001)
    await create_tutor_profile(db_session, user=user, slug="metrika_t", display_name="MT")
    await db_session.commit()
    resp = await client.get("/u/metrika_t")
    body = resp.text
    assert "mc.yandex.ru/metrika/tag.js" in body
    assert "99999999" in body


async def test_book_page_emits_metrika(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _setup_metrika(monkeypatch)
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=92000002)
    tutor = await create_tutor_profile(db_session, user=user, slug="metrika_b", display_name="MB")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    resp = await client.get(f"/u/metrika_b/book/{services[0].id}")
    assert "mc.yandex.ru/metrika/tag.js" in resp.text


async def test_booked_page_fires_goal(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    """После successful booking страница /booked? должна вызвать reachGoal('lessio_booking')."""
    _setup_metrika(monkeypatch)
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=92000003)
    tutor = await create_tutor_profile(db_session, user=user, slug="metrika_g", display_name="MG")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
            client_email="goal@e.com",
            client_full_name="G",
            client_phone=None,
        )
        await db_session.commit()
    resp = await client.get(f"/u/metrika_g/booked?token={booking.manage_token}")
    assert "reachGoal" in resp.text
    assert "lessio_booking" in resp.text


async def test_metrika_no_op_when_id_empty(client: AsyncClient) -> None:
    """В dev (пустой ya_metrika_id) — никаких mc.yandex.ru тегов."""
    resp = await client.get("/lessio")
    assert "mc.yandex.ru/metrika/tag.js" not in resp.text
