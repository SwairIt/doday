"""Lessio cron-driven jobs: reminders 24h + 1h.

Идемпотентный batch: SELECT confirmed bookings в окне (target ± 5 мин), не
имеющие reminder_{hours}h_sent_at. На каждый — `send_reminder_email` (SMTP-fail
не блокирует остальные). UPDATE timestamp только при success.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.email import send_reminder_email
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
