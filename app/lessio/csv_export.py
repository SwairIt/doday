"""CSV export для income tracking (импорт в «Мой Налог» / банковскую отчётность).

Формат строго фиксированный: date,time_utc,client_name,client_email,service,
duration_min,price_rub,payment_status,booking_status. Header — латиница, чтобы
любой CSV-импортёр распарсил без BOM-возни.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from uuid import UUID

from app.lessio.models import LessioBooking


def bookings_to_csv(bookings: Iterable[LessioBooking], *, service_titles: dict[UUID, str]) -> str:
    """Сериализовать bookings в CSV-строку.

    `service_titles` — map service_id → title; caller pre-resolves через SELECT.
    Возвращает строку (router добавит BOM + Content-Disposition).
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        [
            "date",
            "time_utc",
            "client_name",
            "client_email",
            "service",
            "duration_min",
            "price_rub",
            "payment_status",
            "booking_status",
        ]
    )
    for b in bookings:
        writer.writerow(
            [
                b.starts_at.strftime("%Y-%m-%d"),
                b.starts_at.strftime("%H:%M"),
                b.client_full_name,
                b.client_email,
                service_titles.get(b.service_id, "—"),
                b.duration_minutes,
                b.price_kopecks // 100,
                b.payment_status,
                b.status,
            ]
        )
    return out.getvalue()
