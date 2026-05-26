"""Идемпотентный seed «demo» tutor'а для /u/demo живой ссылки с landing page.

Создаёт (или обновляет):
- User: lessio_demo@auto.lessio (password_hash=None, telegram-only style)
- LessioTutorProfile: slug='demo', display_name='Демо-репетитор', niche='english',
  bio описывает что это showcase
- 2 услуги (Английский 60 мин · 1500₽, IELTS Speaking 30 мин · 1000₽)
- 3 client-row'a + 3 completed bookings + 3 reviews для aggregateRating

Использование:
    .venv/bin/python -m scripts.lessio_seed_demo

На проде:
    cd /var/www/getdoday/data/www/getdoday.ru/app
    .venv/bin/python -m scripts.lessio_seed_demo
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.billing import models as _billing  # noqa: F401  register star_payments FK target
from app.config import get_settings
from app.lessio.models import (
    LessioBooking,
    LessioClient,
    LessioReview,
    LessioService,
    LessioTutorProfile,
)

_DEMO_EMAIL = "lessio_demo@auto.lessio"
_DEMO_SLUG = "demo"


async def _seed(session: AsyncSession) -> None:
    # 1. User
    user = (
        await session.execute(select(User).where(User.email == _DEMO_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=_DEMO_EMAIL,
            password_hash=None,
            tier="free",
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        print(f"  + User created: {_DEMO_EMAIL}")
    else:
        print(f"  = User exists: {_DEMO_EMAIL}")

    # 2. LessioTutorProfile
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == _DEMO_SLUG)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = LessioTutorProfile(
            id=uuid4(),
            user_id=user.id,
            slug=_DEMO_SLUG,
            display_name="Демо-репетитор",
            niche="english",
            bio=(
                "Это демо-страница Lessio. Так выглядит профиль настоящего "
                "репетитора для клиента: услуги с ценами, свободные слоты, "
                "отзывы предыдущих учеников. Создайте свою такую же на "
                "/lessio/auth/register — займёт 30 секунд."
            ),
            avatar_emoji="👩‍🏫",
            timezone="Europe/Moscow",
            is_active=True,
        )
        session.add(profile)
        await session.flush()
        print(f"  + Profile created: /u/{_DEMO_SLUG}")
    else:
        print(f"  = Profile exists: /u/{_DEMO_SLUG}")

    # 3. Services — два примера
    services_spec = [
        {
            "title": "Английский · урок 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 150000,
            "price_stars": 1250,
        },
        {
            "title": "Mock IELTS Speaking · 30 мин",
            "duration_minutes": 30,
            "price_kopecks": 100000,
            "price_stars": 833,
        },
    ]
    services: list[LessioService] = []
    for spec in services_spec:
        existing = (
            await session.execute(
                select(LessioService).where(
                    LessioService.tutor_id == profile.id,
                    LessioService.title == spec["title"],
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            svc = LessioService(tutor_id=profile.id, **spec)
            session.add(svc)
            await session.flush()
            services.append(svc)
            print(f"  + Service: {spec['title']}")
        else:
            services.append(existing)
            print(f"  = Service exists: {spec['title']}")

    # 4. Fake clients + completed bookings + reviews — для aggregateRating
    review_data = [
        (
            "Анна",
            "anna@demo.example.com",
            5,
            "Лучший репетитор английского что у меня был! За месяц подтянула грамматику до уровня собеседования. Очень рекомендую.",
            services[0],
        ),
        (
            "Михаил",
            "misha@demo.example.com",
            5,
            "Готовились к IELTS Speaking — сдал на 7.5. Понятные пояснения, разбор моих типичных ошибок. Спасибо!",
            services[1],
        ),
        (
            "Екатерина",
            "kate@demo.example.com",
            4,
            "Хорошие уроки, всегда вовремя. Иногда хотелось бы больше домашних заданий, но в целом — рекомендую.",
            services[0],
        ),
    ]
    for i, (name, email, rating, text, service) in enumerate(review_data):
        # Client
        client = (
            await session.execute(
                select(LessioClient).where(
                    LessioClient.tutor_id == profile.id, LessioClient.email == email
                )
            )
        ).scalar_one_or_none()
        if client is None:
            client = LessioClient(
                tutor_id=profile.id,
                email=email,
                full_name=name,
                phone=None,
                telegram_user_id=None,
            )
            session.add(client)
            await session.flush()

        # Booking (completed, в прошлом)
        booking = (
            await session.execute(
                select(LessioBooking).where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.client_id == client.id,
                    LessioBooking.service_id == service.id,
                )
            )
        ).scalar_one_or_none()
        if booking is None:
            past_slot = datetime.now(UTC) - timedelta(days=7 + i * 3, hours=2)
            booking = LessioBooking(
                tutor_id=profile.id,
                client_id=client.id,
                service_id=service.id,
                starts_at=past_slot,
                duration_minutes=service.duration_minutes,
                status="completed",
                completed_at=past_slot + timedelta(minutes=service.duration_minutes),
                price_kopecks=service.price_kopecks,
                price_stars=service.price_stars,
                manage_token=secrets.token_urlsafe(48),
                payment_status="paid",
                paid_at=past_slot + timedelta(minutes=service.duration_minutes),
                client_email=email,
                client_full_name=name,
            )
            session.add(booking)
            await session.flush()

        # Review
        review = (
            await session.execute(select(LessioReview).where(LessioReview.booking_id == booking.id))
        ).scalar_one_or_none()
        if review is None:
            review = LessioReview(
                booking_id=booking.id,
                tutor_id=profile.id,
                client_email=email,
                client_full_name=name,
                rating=rating,
                text=text,
            )
            session.add(review)
            print(f"  + Review by {name} ({rating}/5)")
        else:
            print(f"  = Review by {name} exists")

    await session.commit()
    print(f"\nDONE: demo seed complete - visit /u/{_DEMO_SLUG}")


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        await _seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
