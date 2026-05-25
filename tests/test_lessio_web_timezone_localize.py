"""Slot pickers + booking confirm: time strings include data-utc-iso attr for client-side TZ-localize."""

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


async def test_book_page_slots_have_data_utc_iso(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=91000001)
    tutor = await create_tutor_profile(db_session, user=user, slug="tz_book", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    resp = await client.get(f"/u/tz_book/book/{services[0].id}")
    body = resp.text
    # Slot buttons должны иметь data-utc-iso для client-side localize
    assert "data-utc-iso" in body
    # JS-hook class присутствует среди классов кнопки
    assert "lessio-localize" in body


async def test_booked_page_has_data_utc_iso(client: AsyncClient, db_session: AsyncSession) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=91000002)
    tutor = await create_tutor_profile(db_session, user=user, slug="tz_booked", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
            client_email="tz@e.com",
            client_full_name="TZ",
            client_phone=None,
        )
        await db_session.commit()
    resp = await client.get(f"/u/tz_booked/booked?token={booking.manage_token}")
    assert resp.status_code == 200
    assert "data-utc-iso" in resp.text


async def test_lessio_localize_script_loaded_on_public_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=91000003)
    tutor = await create_tutor_profile(db_session, user=user, slug="tz_script", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    resp = await client.get(f"/u/tz_script/book/{services[0].id}")
    # Inline JS должен присутствовать чтобы преобразовать UTC → local
    body = resp.text
    assert "toLocaleString" in body or "Intl.DateTimeFormat" in body
