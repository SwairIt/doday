"""Lessio service-layer: auto-onboarding, slot search, booking-invoice creation.

Validation-phase: реально используется только `auto_onboard_tutor`. Booking-функции
(`find_free_slots`, `create_booking_invoice`) — stub'ы под MVP, добавятся
после ≥100 waitlist по 2026-06-01.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.lessio.models import LessioBooking, LessioService, LessioTutorProfile
from app.telegram.models import TelegramLink


class OnboardError(Exception):
    """Auto-onboard fails — пробрасывается до router который вернёт 400/409."""


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,49}$")


def validate_slug(slug: str) -> bool:
    """URL-safe handle: 3-50 chars, lowercase + digits + - + _, starts with alnum."""
    return bool(_SLUG_RE.match(slug))


async def auto_onboard_tutor(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    telegram_first_name: str | None = None,
    telegram_username: str | None = None,
) -> tuple[User, LessioTutorProfile | None]:
    """Идемпотентный auto-onboard от Telegram WebApp initData.

    Шаги:
    1. Find user by `TelegramLink.chat_id == telegram_user_id` (Doday-схема —
       Telegram-связь хранится в отдельной таблице `telegram_links`, не в users).
    2. Если нет — создать User + TelegramLink одной транзакцией. Email = placeholder
       `lessio_tg_<id>@auto.lessio`, password_hash = NULL (Telegram-only).
    3. Touch `User.telegram_first_name/username` через TelegramLink (data lives там).
    4. Возвращаем (user, tutor_profile_or_None). Если профиля нет — router редиректит
       на /lessio/miniapp/onboard.

    Не raise если что-то уже есть (IntegrityError → fetch existing).
    """
    _ = telegram_first_name, telegram_username  # пока не используются — TelegramLink не хранит имя

    link = (
        await session.execute(select(TelegramLink).where(TelegramLink.chat_id == telegram_user_id))
    ).scalar_one_or_none()

    user: User | None
    if link is not None:
        user = await session.get(User, link.user_id)
        if user is None:
            # FK orphan — корраптeд состояние. Reset.
            await session.delete(link)
            await session.flush()
            link = None

    if link is None:
        placeholder_email = f"lessio_tg_{telegram_user_id}@auto.lessio"
        user = User(
            email=placeholder_email,
            password_hash=None,  # Telegram-only — нет пароля
            tier="free",
            email_verified_at=datetime.now(UTC),  # Telegram доверенный источник
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            # Race: другая coroutine создала. Refetch by email.
            await session.rollback()
            refetched = (
                await session.execute(select(User).where(User.email == placeholder_email))
            ).scalar_one_or_none()
            if refetched is None:
                raise
            user = refetched
        link = TelegramLink(user_id=user.id, chat_id=telegram_user_id, linked_at=datetime.now(UTC))
        session.add(link)
        try:
            await session.flush()
        except IntegrityError:
            # Race на TelegramLink.chat_id UNIQUE.
            await session.rollback()
            link = (
                await session.execute(
                    select(TelegramLink).where(TelegramLink.chat_id == telegram_user_id)
                )
            ).scalar_one()
            user = await session.get(User, link.user_id)
            if user is None:
                raise OnboardError("FK orphan: telegram_link без user") from None

    if user is None:  # narrowing — never None after if/else above
        raise OnboardError("auto_onboard_tutor produced None user (impossible state)")
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()

    return user, profile


async def create_tutor_profile(
    session: AsyncSession,
    *,
    user: User,
    slug: str,
    display_name: str,
    niche: str = "other",
    bio: str | None = None,
) -> LessioTutorProfile:
    """Создать `LessioTutorProfile` после онбординга. Slug должен быть уникальным."""
    if not validate_slug(slug):
        raise OnboardError(
            "slug должен быть 3-50 символов, только латиница/цифры/дефис/подчёркивание"
        )
    profile = LessioTutorProfile(
        user_id=user.id,
        slug=slug.lower(),
        display_name=display_name[:100],
        niche=niche if niche else "other",
        bio=(bio or "")[:1000] or None,
    )
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise OnboardError(f"slug «{slug}» уже занят — выберите другой") from exc
    return profile


async def is_slug_available(session: AsyncSession, slug: str) -> bool:
    """Check свободен ли slug. Использует тот же regex что create_tutor_profile."""
    if not validate_slug(slug):
        return False
    existing = (
        await session.execute(
            select(LessioTutorProfile.id).where(LessioTutorProfile.slug == slug.lower())
        )
    ).scalar_one_or_none()
    return existing is None


# ---------------------------------------------------------------------------
# Booking — stub'ы под MVP-фазу.
# ---------------------------------------------------------------------------


async def find_free_slots(
    session: AsyncSession,
    tutor: LessioTutorProfile,
    *,
    date_from: datetime,
    date_to: datetime,
    duration_minutes: int = 60,
) -> list[datetime]:
    """Вернуть свободные слоты репетитора в диапазоне.

    MVP-stub: возвращает пустой список. Реальная имплементация:
    - Парсит tutor.working_days + work_start/end_minute + buffer_minutes
    - Вычитает существующие LessioBooking'и с status in (pending_payment, paid)
    - Учитывает timezone tutor'а
    """
    return []


async def create_booking_invoice(
    session: AsyncSession,
    *,
    tutor_id: UUID,
    client_telegram_user_id: int,
    service_id: UUID,
    starts_at: datetime,
) -> str:
    """Создать Stars-invoice URL для booking'а. MVP-stub.

    Реальная имплементация:
    - Найти/создать LessioClient (per-tutor unique by telegram_user_id)
    - Создать LessioBooking с status='pending_payment'
    - Через app.billing.stars.create_invoice_link выписать invoice на @LessioBot
      с product_code = ad-hoc `lessio_booking_<booking_id>` (динамический продукт)
    - Сохранить invoice URL + LessioBooking.star_payment_id когда придёт SuccessfulPayment

    Сейчас — raise NotImplementedError чтобы router падал чисто.
    """
    raise NotImplementedError("booking flow — MVP-фаза, не валидация")


# Re-export для router-layer.
__all__ = [
    "LessioBooking",
    "LessioService",
    "LessioTutorProfile",
    "OnboardError",
    "auto_onboard_tutor",
    "create_booking_invoice",
    "create_tutor_profile",
    "find_free_slots",
    "is_slug_available",
    "validate_slug",
]
