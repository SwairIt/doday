"""Lessio cron-driven jobs: reminders 24h + 1h.

Идемпотентный batch: SELECT confirmed bookings в окне (target ± 5 мин), не
имеющие reminder_{hours}h_sent_at. На каждый — `send_reminder_email` (SMTP-fail
не блокирует остальные). UPDATE timestamp только при success.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.email import (
    send_daily_digest_email,
    send_reminder_email,
    send_review_request_email,
)
from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile

_log = structlog.get_logger(__name__)


async def dispatch_reminders(session: AsyncSession, *, hours: int) -> dict[str, Any]:
    """Send reminder emails для confirmed bookings в окне (target ± 5 мин).

    Caller обязан вызвать `session.commit()` после успеха.
    """
    now = datetime.now(UTC)
    target = now + timedelta(hours=hours)
    window_start = target - timedelta(minutes=5)
    window_end = target + timedelta(minutes=5)
    field = LessioBooking.reminder_24h_sent_at if hours == 24 else LessioBooking.reminder_1h_sent_at

    bookings = (
        (
            await session.execute(
                select(LessioBooking).where(
                    LessioBooking.status == "confirmed",
                    LessioBooking.starts_at >= window_start,
                    LessioBooking.starts_at <= window_end,
                    field.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    sent = 0
    failed = 0
    for b in bookings:
        tutor = await session.get(LessioTutorProfile, b.tutor_id)
        service = await session.get(LessioService, b.service_id)
        if tutor is None or service is None:
            failed += 1
            continue
        ok = await send_reminder_email(
            booking=b, tutor=tutor, service_title=service.title, hours=hours
        )
        if ok:
            if hours == 24:
                b.reminder_24h_sent_at = datetime.now(UTC)
            else:
                b.reminder_1h_sent_at = datetime.now(UTC)
            sent += 1
        else:
            failed += 1
    await session.flush()
    _log.info(
        "lessio_reminders_dispatched",
        hours=hours,
        sent=sent,
        failed=failed,
        total=len(bookings),
    )
    return {"sent": sent, "failed": failed, "total": len(bookings)}


async def mark_completed_bookings(session: AsyncSession) -> dict[str, Any]:
    """Confirmed booking чьё время (starts_at + duration) прошло → mark 'completed' +
    запросить отзыв клиента (send_review_request_email).

    Idempotent — status-transition (confirmed→completed) случается один раз;
    при повторном запуске cron-а bookings уже не в выборке.
    """
    now = datetime.now(UTC)
    # Используем func.make_interval/строку для duration в минутах в WHERE-клозе
    # Простой подход: select all confirmed, фильтр в Python (count небольшой).
    candidates = (
        (
            await session.execute(
                select(LessioBooking).where(
                    LessioBooking.status == "confirmed",
                    LessioBooking.starts_at < now,  # начались
                )
            )
        )
        .scalars()
        .all()
    )

    completed = 0
    email_sent = 0
    email_failed = 0
    for b in candidates:
        end_time = b.starts_at + timedelta(minutes=b.duration_minutes)
        if end_time > now:
            continue  # ещё идёт
        b.status = "completed"
        b.completed_at = now
        completed += 1
        # Отправить review-email (one-shot)
        tutor = await session.get(LessioTutorProfile, b.tutor_id)
        service = await session.get(LessioService, b.service_id)
        if tutor is None or service is None:
            continue
        try:
            ok = await send_review_request_email(
                booking=b, tutor=tutor, service_title=service.title
            )
            if ok:
                email_sent += 1
            else:
                email_failed += 1
        except Exception as exc:
            _log.warning("lessio_review_email_failed", booking_id=str(b.id), error=str(exc))
            email_failed += 1
    await session.flush()
    _log.info(
        "lessio_mark_completed",
        completed=completed,
        review_emails_sent=email_sent,
        review_emails_failed=email_failed,
    )
    return {
        "completed": completed,
        "review_emails_sent": email_sent,
        "review_emails_failed": email_failed,
    }


# Backwards-compat alias: spec назывался dispatch_review_requests,
# но фактически делает mark+email одной transaction'ой.
dispatch_review_requests = mark_completed_bookings


async def audit_unpaid_bookings(session: AsyncSession) -> dict[str, Any]:
    """Метрика «сколько висит неоплаченных bookings».

    НЕ отменяем автоматически — tutor может принимать оплату нал/СБП на самой
    встрече, и cron-cancel сломает его flow. Зато считаем по 3 категориям:

    - `future_unpaid` — впереди, может быть нормально (ещё не пришло время)
    - `stale_unpaid_24h` — впереди но висит >24ч с момента бронирования
    - `past_unpaid` — прошедшие, должны были провести и отметить «оплачено»

    Цифры идут в structlog → Sentry alert если резко выросли (spam-bots).
    Tutor видит свои unpaid в кабинете (Сегодня / Клиенты — payment_status).
    """
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(hours=24)

    future_unpaid = (
        (
            await session.execute(
                select(LessioBooking).where(
                    LessioBooking.status == "confirmed",
                    LessioBooking.payment_status == "unpaid",
                    LessioBooking.starts_at > now,
                )
            )
        )
        .scalars()
        .all()
    )

    stale_unpaid_24h = [b for b in future_unpaid if b.created_at < stale_cutoff]

    past_unpaid = (
        (
            await session.execute(
                select(LessioBooking).where(
                    LessioBooking.status == "confirmed",
                    LessioBooking.payment_status == "unpaid",
                    LessioBooking.starts_at <= now,
                )
            )
        )
        .scalars()
        .all()
    )

    _log.info(
        "lessio_unpaid_audit",
        future_unpaid=len(future_unpaid),
        stale_unpaid_24h=len(stale_unpaid_24h),
        past_unpaid=len(past_unpaid),
    )
    # Sentry-alert threshold — резкий рост может означать спам-bot бронирующий
    # слоты без оплаты. 50+ unpaid за сутки на новой инсталляции — anomaly.
    if len(stale_unpaid_24h) > 50:
        _log.warning(
            "lessio_unpaid_spike",
            stale_unpaid_24h=len(stale_unpaid_24h),
            message="Possible spam-bot bookings — manual review recommended",
        )
    return {
        "future_unpaid": len(future_unpaid),
        "stale_unpaid_24h": len(stale_unpaid_24h),
        "past_unpaid": len(past_unpaid),
    }


async def dispatch_daily_digests(session: AsyncSession) -> dict[str, Any]:
    """Утренний digest: для каждого tutor'а с notification_email и confirmed-bookings
    на сегодня (в его tz) → шлём список встреч.

    Не идемпотентный: cron должен запускаться раз в день (через cron-poll
    можно ограничить через флаг или WHERE-clause в будущем). В MVP принимаем что
    дёрнут его раз в утро (e.g. 06:00 MSK).
    """
    now = datetime.now(UTC)
    # Idempotency: skip если digest уже шёл < 20h назад
    twenty_hours_ago = now - timedelta(hours=20)
    tutors = (
        (
            await session.execute(
                select(LessioTutorProfile).where(
                    LessioTutorProfile.is_active.is_(True),
                    LessioTutorProfile.notification_email.is_not(None),
                    (LessioTutorProfile.last_daily_digest_at.is_(None))
                    | (LessioTutorProfile.last_daily_digest_at < twenty_hours_ago),
                )
            )
        )
        .scalars()
        .all()
    )

    sent = 0
    failed = 0
    for tutor in tutors:
        try:
            tz = ZoneInfo(tutor.timezone)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
        now_local = now.astimezone(tz)
        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = day_start_local.astimezone(UTC)
        today_end = (day_start_local + timedelta(days=1)).astimezone(UTC)

        bookings = (
            (
                await session.execute(
                    select(LessioBooking)
                    .where(
                        LessioBooking.tutor_id == tutor.id,
                        LessioBooking.starts_at >= today_start,
                        LessioBooking.starts_at < today_end,
                        LessioBooking.status == "confirmed",
                    )
                    .order_by(LessioBooking.starts_at)
                )
            )
            .scalars()
            .all()
        )
        if not bookings:
            continue
        # Enrich для шаблона: local_time + service_title + client_name
        booking_views = []
        for b in bookings:
            service = await session.get(LessioService, b.service_id)
            booking_views.append(
                {
                    "local_time": b.starts_at.astimezone(tz).strftime("%H:%M"),
                    "client_name": b.client_full_name,
                    "service_title": service.title if service else "—",
                    "duration_minutes": b.duration_minutes,
                }
            )

        tz_label = day_start_local.strftime("%Z") or tutor.timezone
        try:
            # filter уже отсёк None — но mypy не знает, поэтому fallback
            recipient = tutor.notification_email or ""
            if not recipient:
                continue
            ok = await send_daily_digest_email(
                tutor=tutor,
                to=recipient,
                bookings_today=booking_views,  # type: ignore[arg-type]
                timezone_label=tz_label,
            )
            if ok:
                tutor.last_daily_digest_at = now
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            _log.warning("lessio_digest_failed", tutor_id=str(tutor.id), error=str(exc))
            failed += 1
    await session.flush()

    _log.info("lessio_daily_digests_dispatched", sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}
