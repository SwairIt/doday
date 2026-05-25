"""Lessio reviews service — create_review, get_tutor_aggregate.

Один review per booking (DB UNIQUE). Только completed-bookings reviewable —
гарантия что встреча правда состоялась. Aggregate (count + avg) используется
в JSON-LD schema.org/AggregateRating на /u/<slug>.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioReview


class ReviewError(Exception):
    """Validation failed (rating out of 1..5, booking не завершена, и т.д.)."""


async def create_review(
    session: AsyncSession,
    *,
    booking: LessioBooking,
    rating: int,
    text: str | None,
) -> LessioReview:
    """Создать отзыв для завершённой встречи. Raise ReviewError при invalid input."""
    if booking.status != "completed":
        raise ReviewError("Встреча не завершена — отзыв оставить нельзя")
    if not (1 <= rating <= 5):
        raise ReviewError("оценка должна быть от 1 до 5")
    review = LessioReview(
        booking_id=booking.id,
        tutor_id=booking.tutor_id,
        client_email=booking.client_email,
        client_full_name=booking.client_full_name,
        rating=rating,
        text=(text or "").strip()[:2000] or None,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ReviewError("Отзыв на эту встречу уже оставлен") from exc
    return review


async def get_tutor_aggregate(session: AsyncSession, *, tutor_id: UUID) -> dict[str, Any]:
    """Returns {'count': int, 'avg': float | None}. avg=None если count=0."""
    row = (
        await session.execute(
            select(
                func.count(LessioReview.id),
                func.avg(LessioReview.rating),
            ).where(LessioReview.tutor_id == tutor_id)
        )
    ).one()
    count, avg = row
    return {
        "count": int(count or 0),
        "avg": float(avg) if avg is not None else None,
    }


async def get_tutor_recent_reviews(
    session: AsyncSession, *, tutor_id: UUID, limit: int = 5
) -> list[LessioReview]:
    """Последние N reviews для отображения на /u/<slug>."""
    return list(
        (
            await session.execute(
                select(LessioReview)
                .where(LessioReview.tutor_id == tutor_id)
                .order_by(LessioReview.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
