"""Lessio reviews: create_review, get_aggregate, public review-submit flow, aggregateRating в JSON-LD."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioReview, LessioService, LessioTutorProfile
from app.lessio.reviews import ReviewError, create_review, get_tutor_aggregate
from app.lessio.service import (
    auto_onboard_tutor,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _booking(
    db_session: AsyncSession, *, tg_id: int, status: str = "completed"
) -> tuple[LessioTutorProfile, LessioBooking]:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"rev_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session,
            tutor=tutor,
            service=services[0],
            slot=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
            client_email="rev@e.com",
            client_full_name="Reviewer",
            client_phone=None,
        )
        await db_session.commit()
    booking.status = status
    if status == "completed":
        booking.completed_at = datetime.now(UTC)
    await db_session.commit()
    return tutor, booking


# ── Service-level: create_review + aggregate ──────────────────────────


async def test_create_review_for_completed_booking(db_session: AsyncSession) -> None:
    tutor, booking = await _booking(db_session, tg_id=94000001)
    review = await create_review(
        db_session, booking=booking, rating=5, text="Отлично провёл занятие"
    )
    await db_session.commit()
    assert review.rating == 5
    assert review.text == "Отлично провёл занятие"
    assert review.tutor_id == tutor.id
    assert review.client_email == booking.client_email


async def test_create_review_rejects_non_completed_booking(
    db_session: AsyncSession,
) -> None:
    _, booking = await _booking(db_session, tg_id=94000002, status="confirmed")
    with pytest.raises(ReviewError, match="не завершена"):
        await create_review(db_session, booking=booking, rating=4, text=None)


async def test_create_review_rejects_invalid_rating(db_session: AsyncSession) -> None:
    _, booking = await _booking(db_session, tg_id=94000003)
    with pytest.raises(ReviewError, match="оценка"):
        await create_review(db_session, booking=booking, rating=0, text=None)
    with pytest.raises(ReviewError, match="оценка"):
        await create_review(db_session, booking=booking, rating=6, text=None)


async def test_create_review_idempotent_per_booking(
    db_session: AsyncSession,
) -> None:
    _, booking = await _booking(db_session, tg_id=94000004)
    await create_review(db_session, booking=booking, rating=5, text="First")
    await db_session.commit()
    with pytest.raises(ReviewError, match="уже оставлен"):
        await create_review(db_session, booking=booking, rating=3, text="Second")


async def test_get_tutor_aggregate_returns_count_and_avg(
    db_session: AsyncSession,
) -> None:
    tutor, b1 = await _booking(db_session, tg_id=94000005)
    # Создадим ещё пару booking'ов для тех же tutor + reviews
    s = (
        (await db_session.execute(select(LessioService).where(LessioService.tutor_id == tutor.id)))
        .scalars()
        .first()
    )
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        b2 = await create_booking(
            db_session,
            tutor=tutor,
            service=s,
            slot=datetime(2026, 6, 2, 14, 0, tzinfo=UTC),
            client_email="r2@e.com",
            client_full_name="R2",
            client_phone=None,
        )
        b3 = await create_booking(
            db_session,
            tutor=tutor,
            service=s,
            slot=datetime(2026, 6, 3, 14, 0, tzinfo=UTC),
            client_email="r3@e.com",
            client_full_name="R3",
            client_phone=None,
        )
        await db_session.commit()
    for b in (b2, b3):
        b.status = "completed"
        b.completed_at = datetime.now(UTC)
    await db_session.commit()

    await create_review(db_session, booking=b1, rating=5, text=None)
    await create_review(db_session, booking=b2, rating=4, text=None)
    await create_review(db_session, booking=b3, rating=3, text=None)
    await db_session.commit()

    agg = await get_tutor_aggregate(db_session, tutor_id=tutor.id)
    assert agg["count"] == 3
    assert agg["avg"] == pytest.approx(4.0)


# ── Router-level: /lessio/review/<token> GET + POST ─────────────────────


async def test_review_page_renders_for_completed_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, booking = await _booking(db_session, tg_id=94000010)
    resp = await client.get(f"/lessio/review/{booking.manage_token}")
    assert resp.status_code == 200
    body = resp.text
    assert 'name="rating"' in body
    assert 'name="text"' in body


async def test_review_page_404_for_unknown_token(client: AsyncClient) -> None:
    resp = await client.get("/lessio/review/" + "z" * 64)
    assert resp.status_code == 404


async def test_review_post_creates_review(client: AsyncClient, db_session: AsyncSession) -> None:
    _, booking = await _booking(db_session, tg_id=94000011)
    resp = await client.post(
        f"/lessio/review/{booking.manage_token}",
        data={"rating": "5", "text": "Огонь"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    review = (
        await db_session.execute(select(LessioReview).where(LessioReview.booking_id == booking.id))
    ).scalar_one()
    assert review.rating == 5
    assert review.text == "Огонь"


# ── Public profile: aggregateRating в JSON-LD ──────────────────────────


async def test_profile_renders_aggregate_rating_when_reviews_exist(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor, booking = await _booking(db_session, tg_id=94000020)
    await create_review(db_session, booking=booking, rating=5, text="Amazing")
    await db_session.commit()

    resp = await client.get(f"/u/{tutor.slug}")
    body = resp.text
    assert "aggregateRating" in body
    assert "ratingValue" in body
    assert "reviewCount" in body


async def test_profile_no_aggregate_when_no_reviews(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=94000021)
    await create_tutor_profile(db_session, user=user, slug="no_rev_t", display_name="NoRev")
    await db_session.commit()
    resp = await client.get("/u/no_rev_t")
    body = resp.text
    assert "aggregateRating" not in body
