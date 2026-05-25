"""Lessio email-уведомления — booking confirm/cancel + reminders.

Все async-функции ловят SMTPError и логируют — отправка email никогда не должна
блокировать booking-транзакцию или cron-batch. `send_reminder_email` возвращает
bool чтобы caller знал, можно ли проставить `reminder_*_sent_at` timestamp.
"""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.lessio.models import LessioBooking, LessioTutorProfile

_log = structlog.get_logger(__name__)

_env = Environment(
    loader=FileSystemLoader("app/templates/lessio/email"),
    autoescape=select_autoescape(["html"]),
)


def _base_url() -> str:
    return get_settings().app_base_url.rstrip("/")


async def _send(*, to: str, subject: str, html: str, text: str) -> bool:
    """Returns True on success, False on SMTP failure (logged, not raised)."""
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = f"Lessio <{settings.smtp_from}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_start_tls,
        )
        return True
    except Exception as exc:
        _log.warning("lessio_email_send_failed", to=to, subject=subject, error=str(exc))
        return False


def _ctx(booking: LessioBooking, tutor: LessioTutorProfile, **extra: Any) -> dict[str, Any]:
    base = _base_url()
    return {
        "tutor": tutor,
        "booking": booking,
        "manage_url": f"{base}/lessio/manage/{booking.manage_token}",
        "profile_url": f"{base}/u/{tutor.slug}",
        "cabinet_url": f"{base}/lessio/app/today",
        "meeting_url": booking.meeting_url or tutor.default_meeting_url_template or "",
        **extra,
    }


async def send_booking_emails(
    *, booking: LessioBooking, tutor: LessioTutorProfile, service_title: str
) -> None:
    """Двойная рассылка после нового booking: клиенту + репетитору (если notification_email)."""
    ctx = _ctx(booking, tutor, service_title=service_title)

    client_html = _env.get_template("booking_confirmed.html").render(**ctx)
    client_text = _env.get_template("booking_confirmed.txt").render(**ctx)
    await _send(
        to=booking.client_email,
        subject=f"Вы записаны: {service_title} · {tutor.display_name}",
        html=client_html,
        text=client_text,
    )

    tutor_email = tutor.notification_email or ""
    if tutor_email:
        tutor_html = _env.get_template("new_booking.html").render(**ctx)
        tutor_text = _env.get_template("new_booking.txt").render(**ctx)
        await _send(
            to=tutor_email,
            subject=f"Новая запись: {booking.client_full_name} · {service_title}",
            html=tutor_html,
            text=tutor_text,
        )


async def send_cancellation_email(
    *,
    booking: LessioBooking,
    tutor: LessioTutorProfile,
    by: str,
    service_title: str,
) -> None:
    """by ∈ {client, tutor} — определяет получателя противоположной стороны."""
    ctx = _ctx(booking, tutor, service_title=service_title, cancelled_by=by)
    if by == "client":
        tmpl = "cancelled_by_client"
        to = tutor.notification_email or ""
        subject = f"Отмена записи: {booking.client_full_name} · {service_title}"
    else:
        tmpl = "cancelled_by_tutor"
        to = booking.client_email
        subject = f"Ваша запись отменена · {tutor.display_name}"
    if not to:
        return
    html = _env.get_template(f"{tmpl}.html").render(**ctx)
    text = _env.get_template(f"{tmpl}.txt").render(**ctx)
    await _send(to=to, subject=subject, html=html, text=text)


async def send_reminder_email(
    *,
    booking: LessioBooking,
    tutor: LessioTutorProfile,
    service_title: str,
    hours: int,
) -> bool:
    """24h или 1h reminder клиенту. Returns True если SMTP ok (для UPDATE timestamp)."""
    ctx = _ctx(booking, tutor, service_title=service_title, hours=hours)
    tmpl = "reminder_24h" if hours == 24 else "reminder_1h"
    html = _env.get_template(f"{tmpl}.html").render(**ctx)
    text = _env.get_template(f"{tmpl}.txt").render(**ctx)
    subject_prefix = "Завтра в" if hours == 24 else "Через час:"
    subject = f"{subject_prefix} {service_title} · {tutor.display_name}"
    return await _send(to=booking.client_email, subject=subject, html=html, text=text)


async def send_review_request_email(
    *, booking: LessioBooking, tutor: LessioTutorProfile, service_title: str
) -> bool:
    """После завершения встречи — просьба оценить (magic-link на review-форму)."""
    ctx = _ctx(booking, tutor, service_title=service_title)
    # review-URL переиспользует тот же manage_token
    ctx["review_url"] = ctx["manage_url"].replace("/lessio/manage/", "/lessio/review/")
    html = _env.get_template("review_request.html").render(**ctx)
    text = _env.get_template("review_request.txt").render(**ctx)
    subject = f"Как прошла встреча с {tutor.display_name}? · Lessio"
    return await _send(to=booking.client_email, subject=subject, html=html, text=text)
