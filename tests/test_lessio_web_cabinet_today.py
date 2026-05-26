"""Lessio cabinet: /lessio/app/today — today bookings list + auth-required."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.lessio.models import LessioService, LessioTutorProfile
from app.lessio.service import create_booking


async def _register_and_setup(client: AsyncClient, *, tg_id: int) -> str:
    """Register + setup-profile через web-flow, возвращает slug."""
    slug = f"today_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"t{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_today_redirects_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/today", follow_redirects=False)
    assert resp.status_code in (401, 302, 303)


async def test_today_shows_upcoming_bookings(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _register_and_setup(client, tg_id=70000002)

    user = (
        await db_session.execute(select(User).where(User.email == "t70000002@e.com"))
    ).scalar_one()
    tutor = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one()
    service = (
        (await db_session.execute(select(LessioService).where(LessioService.tutor_id == tutor.id)))
        .scalars()
        .first()
    )
    assert service is not None

    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        # «Сегодня» считается в tutor TZ (default Europe/Moscow); используем MSK 14:00
        # чтобы тест был детерминированным независимо от UTC времени запуска.
        from zoneinfo import ZoneInfo

        msk_today = datetime.now(ZoneInfo("Europe/Moscow")).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        today_slot = msk_today.astimezone(UTC)
        await create_booking(
            db_session,
            tutor=tutor,
            service=service,
            slot=today_slot,
            client_email="cust@e.com",
            client_full_name="Customer Today",
            client_phone=None,
        )
        await db_session.commit()

    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    assert "Customer Today" in resp.text
    assert slug in resp.text  # sidebar shows public link


async def test_today_empty_state(client: AsyncClient, db_session: AsyncSession) -> None:
    await _register_and_setup(client, tg_id=70000003)
    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    assert "пока нет" in resp.text.lower() or "встреч" in resp.text.lower()


async def test_today_shows_onboarding_checklist_for_new_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Свежий tutor без bio/booking'ов должен видеть стартовый чек-лист."""
    await _register_and_setup(client, tg_id=70000010)
    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    body = resp.text
    assert "Стартовый чек-лист" in body
    # Все 5 шагов должны быть отрисованы
    assert "Заполните «О себе»" in body
    assert "Проверьте услуги" in body
    assert "Настройте рабочие дни" in body
    assert (
        "email для уведомлений" in body
        or "Email для уведомлений" in body
        or "Добавьте email" in body
    )
    assert "Получите первую запись" in body
    # Прогресс — частичный (хотя бы 0/5 виден)
    assert "0/5" in body or "1/5" in body or "2/5" in body


async def test_today_checklist_marks_steps_complete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Заполнили bio + email + получили booking → чеклист обновляется."""
    slug = await _register_and_setup(client, tg_id=70000011)
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    profile.bio = "x" * 60  # ≥ 50 chars
    profile.notification_email = "tutor@example.com"
    await db_session.commit()

    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    body = resp.text
    # 4 done из 5 (bio, services [auto], schedule [default], email — booking ещё нет)
    # Либо «4/5» либо «Последний шаг до полной готовности»
    assert "4/5" in body or "Последний шаг" in body or "Почти готово" in body
