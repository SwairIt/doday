"""RFC5545 iCalendar export для tutor'а — confirmed bookings как VEVENTs.

Tutor подписывается на свой feed в Apple Calendar / Outlook / Google Calendar.
Любые updates booking'ов появятся при следующем refresh (обычно каждые 15 мин).

URL format: /lessio/app/calendar.ics?token=<calendar_feed_token>
Token = encrypt(profile.id) через Fernet (тот же что Google Calendar).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from app.lessio.models import LessioBooking, LessioTutorProfile


def _ics_datetime(dt: datetime) -> str:
    """Format datetime в UTC iCal format (e.g. '20260601T140000Z')."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _ics_escape(text: str) -> str:
    """Escape iCal text — backslash, comma, semicolon, newline."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def bookings_to_ical(
    *,
    tutor: LessioTutorProfile,
    bookings: Iterable[LessioBooking],
    service_titles: dict[UUID, str],
    base_url: str,
) -> str:
    """Сериализовать список confirmed bookings → ical-feed string."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lessio//Tutor Schedule//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Lessio · {_ics_escape(tutor.display_name)}",
        f"X-WR-TIMEZONE:{tutor.timezone}",
        "X-WR-CALDESC:Записи через Lessio",
    ]
    for b in bookings:
        title = service_titles.get(b.service_id, "Встреча")
        end_dt = b.starts_at.replace(microsecond=0) + (
            (b.starts_at - b.starts_at).__class__(seconds=b.duration_minutes * 60)
        )
        summary = f"{title} — {b.client_full_name}"
        description_parts = [
            f"Клиент: {b.client_full_name}",
            f"Email: {b.client_email}",
        ]
        if b.notes:
            description_parts.append(f"Комментарий: {b.notes}")
        if b.meeting_url:
            description_parts.append(f"Ссылка: {b.meeting_url}")
        description_parts.append(f"Управление: {base_url}/lessio/manage/{b.manage_token}")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{b.id}@lessio.getdoday.ru",
                f"DTSTAMP:{_ics_datetime(datetime.now(UTC))}",
                f"DTSTART:{_ics_datetime(b.starts_at)}",
                f"DTEND:{_ics_datetime(end_dt)}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(chr(10).join(description_parts))}",
                f"STATUS:{'CONFIRMED' if b.status == 'confirmed' else 'COMPLETED'}",
            ]
        )
        if b.meeting_url:
            lines.append(f"URL:{b.meeting_url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    # RFC5545 требует CRLF
    return "\r\n".join(lines) + "\r\n"
