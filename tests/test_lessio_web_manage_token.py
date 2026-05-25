"""Magic-link manage: /lessio/manage/<token> — view + cancel + reschedule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
    find_free_slots,
)


async def _booked(
    db_session: AsyncSession, *, tg_id: int, slot: datetime | None = None
) -> tuple[LessioTutorProfile, LessioService, LessioBooking]:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"mng_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    if slot is None:
        slot = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=slot,
            client_email="m@e.com",
            client_full_name="M",
            client_phone=None,
        )
        await db_session.commit()
    return tutor, services[0], booking


async def test_manage_page_renders_booking(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, booking = await _booked(db_session, tg_id=50000001)
    resp = await client.get(f"/lessio/manage/{booking.manage_token}")
    assert resp.status_code == 200
    body = resp.text
    assert "m@e.com" in body or "M" in body


async def test_manage_404_for_unknown_token(client: AsyncClient) -> None:
    resp = await client.get("/lessio/manage/" + "z" * 64)
    assert resp.status_code == 404


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
async def test_manage_cancel(
    mock_send: AsyncMock, client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, booking = await _booked(db_session, tg_id=50000002)
    resp = await client.post(
        f"/lessio/manage/{booking.manage_token}/cancel", follow_redirects=False
    )
    assert resp.status_code in (302, 303)
    refreshed = (
        await db_session.execute(select(LessioBooking).where(LessioBooking.id == booking.id))
    ).scalar_one()
    assert refreshed.status == "cancelled"
    assert refreshed.cancelled_at is not None
    mock_send.assert_awaited_once()


async def test_manage_reschedule_page_renders_slots(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, booking = await _booked(db_session, tg_id=50000003)
    resp = await client.get(f"/lessio/manage/{booking.manage_token}/reschedule")
    assert resp.status_code == 200
    assert "data-slot=" in resp.text or "Свободных слотов" in resp.text


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_manage_reschedule_creates_new_booking(
    mock_book: AsyncMock,
    mock_cancel: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tutor, service, booking = await _booked(db_session, tg_id=50000004)
    slots = await find_free_slots(
        db_session,
        tutor,
        date_from=datetime.now(UTC) + timedelta(days=3),
        date_to=datetime.now(UTC) + timedelta(days=10),
        service=service,
    )
    assert slots
    new_slot = slots[0]
    resp = await client.post(
        f"/lessio/manage/{booking.manage_token}/reschedule",
        data={"slot_iso": new_slot.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text

    old = (
        await db_session.execute(select(LessioBooking).where(LessioBooking.id == booking.id))
    ).scalar_one()
    assert old.status == "cancelled"
    actives = (
        (await db_session.execute(select(LessioBooking).where(LessioBooking.status == "confirmed")))
        .scalars()
        .all()
    )
    assert len(actives) == 1
    assert actives[0].starts_at == new_slot
    assert actives[0].id != booking.id
