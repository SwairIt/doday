"""Lessio service-layer: auto-onboarding, slot search, service templates.

Booking-invoice flow (Telegram-Stars) — отдельная фаза, сейчас stub. Web-flow
платит off-platform: тренер создаёт booking сразу со status='confirmed' +
payment_status='unpaid', клиент платит как угодно (СБП/перевод/нал).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, select
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
# Free-slots search
# ---------------------------------------------------------------------------


async def find_free_slots(
    session: AsyncSession,
    tutor: LessioTutorProfile,
    *,
    date_from: datetime,
    date_to: datetime,
    service: LessioService,
) -> list[datetime]:
    """Compute свободные слоты в [date_from, date_to) для услуги.

    Алгоритм:
    1. Кандидаты: для каждого дня диапазона, если weekday в tutor.working_days,
       перебираем start_minute от work_start_minute с шагом
       (service.duration_minutes + buffer_minutes), пока start + duration ≤ work_end.
    2. Фильтр прошлого: slot ≥ now().
    3. Вычитание занятых:
       - Индивидуальная услуга: slot блокируется если пересекается с интервалом
         любого confirmed/completed booking ± buffer_minutes.
       - Групповая (is_group_session=True): slot блокируется только если на тот же
         starts_at набралось ≥ max_attendees booking'ов этой же услуги.
    """
    now = datetime.now(UTC)
    working_days = set(tutor.working_days)
    step = service.duration_minutes + tutor.buffer_minutes

    candidates: list[datetime] = []
    day = date_from.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    while day < date_to:
        if day.isoweekday() in working_days:
            minute = tutor.work_start_minute
            while minute + service.duration_minutes <= tutor.work_end_minute:
                slot = day + timedelta(minutes=minute)
                if slot >= now and slot >= date_from:
                    candidates.append(slot)
                minute += step
        day += timedelta(days=1)

    if not candidates:
        return []

    bookings = (
        (
            await session.execute(
                select(LessioBooking).where(
                    and_(
                        LessioBooking.tutor_id == tutor.id,
                        LessioBooking.status.in_(["confirmed", "completed"]),
                        LessioBooking.starts_at >= candidates[0] - timedelta(hours=24),
                        LessioBooking.starts_at <= candidates[-1] + timedelta(hours=24),
                    )
                )
            )
        )
        .scalars()
        .all()
    )

    busy_intervals: list[tuple[datetime, datetime]] = []
    group_counts: dict[datetime, int] = {}
    for b in bookings:
        if service.is_group_session and b.service_id == service.id:
            group_counts[b.starts_at] = group_counts.get(b.starts_at, 0) + 1
            continue
        start_with_buffer = b.starts_at - timedelta(minutes=tutor.buffer_minutes)
        end_with_buffer = b.starts_at + timedelta(minutes=b.duration_minutes + tutor.buffer_minutes)
        busy_intervals.append((start_with_buffer, end_with_buffer))

    # Group-session опубликованные слоты — клиенты присоединяются к существующим
    # временам, а не выбирают произвольное start_minute (на step grid).
    if service.is_group_session:
        for existing_start in group_counts:
            if (
                existing_start >= max(now, date_from)
                and existing_start < date_to
                and existing_start not in candidates
            ):
                candidates.append(existing_start)

    def is_free(slot: datetime) -> bool:
        if service.is_group_session:
            return group_counts.get(slot, 0) < service.max_attendees
        slot_end = slot + timedelta(minutes=service.duration_minutes)
        for busy_start, busy_end in busy_intervals:
            if slot < busy_end and slot_end > busy_start:
                return False
        return True

    return sorted(s for s in candidates if is_free(s))


# ---------------------------------------------------------------------------
# Service templates — bulk-create дефолт-услуг под нишу
# ---------------------------------------------------------------------------


class _ServiceTemplate(TypedDict, total=False):
    title: str
    duration_minutes: int
    price_kopecks: int
    price_stars: int
    package_size: int
    is_group_session: bool
    max_attendees: int


_SERVICE_TEMPLATES: dict[str, list[_ServiceTemplate]] = {
    "english": [
        {
            "title": "Английский · урок 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 150000,
            "price_stars": 1500,
        },
        {
            "title": "Английский · пакет 4 урока",
            "duration_minutes": 60,
            "price_kopecks": 540000,
            "price_stars": 5400,
            "package_size": 4,
        },
    ],
    "ielts": [
        {
            "title": "IELTS подготовка · 90 мин",
            "duration_minutes": 90,
            "price_kopecks": 250000,
            "price_stars": 2500,
        },
        {
            "title": "Mock IELTS Speaking",
            "duration_minutes": 30,
            "price_kopecks": 100000,
            "price_stars": 1000,
        },
    ],
    "math": [
        {
            "title": "Математика · 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 120000,
            "price_stars": 1200,
        },
    ],
    "school": [
        {
            "title": "ЕГЭ профильный · 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 180000,
            "price_stars": 1800,
        },
    ],
    "fitness": [
        {
            "title": "Персональная тренировка · 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 200000,
            "price_stars": 2000,
        },
    ],
    "psychology": [
        {
            "title": "Консультация · 50 мин",
            "duration_minutes": 50,
            "price_kopecks": 350000,
            "price_stars": 3500,
        },
    ],
    "yoga": [
        {
            "title": "Групповая йога · 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 80000,
            "price_stars": 800,
            "is_group_session": True,
            "max_attendees": 8,
        },
    ],
    "other": [
        {
            "title": "Встреча · 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 150000,
            "price_stars": 1500,
        },
    ],
}


async def create_services_from_template(
    session: AsyncSession,
    *,
    tutor: LessioTutorProfile,
    niche: str,
) -> list[LessioService]:
    """Bulk-create дефолт-услуг под нишу tutor'а (вызывается из setup-profile)."""
    templates = _SERVICE_TEMPLATES.get(niche, _SERVICE_TEMPLATES["other"])
    created: list[LessioService] = []
    for tpl in templates:
        service = LessioService(
            tutor_id=tutor.id,
            title=tpl["title"],
            duration_minutes=tpl["duration_minutes"],
            price_kopecks=tpl["price_kopecks"],
            price_stars=tpl["price_stars"],
            package_size=tpl.get("package_size"),
            is_group_session=tpl.get("is_group_session", False),
            max_attendees=tpl.get("max_attendees", 1),
        )
        session.add(service)
        created.append(service)
    await session.flush()
    return created


# ---------------------------------------------------------------------------
# Booking — stub под Stars-flow (web-flow платит off-platform, см. spec).
# ---------------------------------------------------------------------------


async def create_booking_invoice(
    session: AsyncSession,
    *,
    tutor_id: UUID,
    client_telegram_user_id: int,
    service_id: UUID,
    starts_at: datetime,
) -> str:
    """Stars-invoice URL для booking'а. Активируется в Telegram-only фазе."""
    _ = session, tutor_id, client_telegram_user_id, service_id, starts_at
    raise NotImplementedError("Stars-booking flow — позже, web-flow платит off-platform")


__all__ = [
    "LessioBooking",
    "LessioService",
    "LessioTutorProfile",
    "OnboardError",
    "auto_onboard_tutor",
    "create_booking_invoice",
    "create_services_from_template",
    "create_tutor_profile",
    "find_free_slots",
    "is_slug_available",
    "validate_slug",
]
