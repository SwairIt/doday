# Lessio Web MVP — Week 1: Backend foundations + Public profile + SEO base

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать модель-уровень + публичную страницу репетитора `/u/<slug>` с базовым SEO + flow регистрации/онбординга tutor'а. К концу wk1 любой может зарегистрироваться → создать профиль → получить публичную ссылку для шаринга. Booking flow (форма, email-уведомления) — week 2.

**Architecture:** Web-first внутри Doday-монорепо (`app/lessio/*`). FastAPI + async SQLAlchemy + Jinja2 + HTMX + Tailwind CDN. Расширяем существующие lessio-модели (migration 0042) без alter'а Doday-таблиц. Public-страницы анонимные с SEO (JSON-LD person/service schema, OG-tags, canonical). Кабинет на классическом email+password auth (Doday-стандарт).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 async / Alembic / pydantic 2 / Jinja2 / HTMX / Tailwind CDN / PostgreSQL.

**Spec:** [`docs/superpowers/specs/2026-05-25-lessio-web-mvp-design.md`](../specs/2026-05-25-lessio-web-mvp-design.md)

---

## File Structure (week 1)

**Create:**
- `alembic/versions/0042_lessio_web_expansion.py` — alter lessio_clients/bookings/services/tutor_profiles
- `app/lessio/web_router.py` — новый router для `/lessio/app/setup-profile`, `/u/<slug>`, `/lessio/auth/*` Lessio-specific
- `app/templates/lessio/u/profile.html` — публичная страница репетитора + SEO-блок
- `app/templates/lessio/app/setup_profile.html` — one-time onboarding после register
- `app/templates/lessio/auth/lessio_register.html` — Lessio-брендированный register-page (тонкая обёртка над Doday-auth)
- `tests/test_lessio_web_register.py` — register → setup-profile flow (4 кейса)
- `tests/test_lessio_web_public_profile.py` — `/u/<slug>` рендер + SEO + 404 (4 кейса)
- `tests/test_lessio_web_free_slots.py` — алгоритм `find_free_slots` (8 граничных кейсов)

**Modify:**
- `app/lessio/models.py` — добавить новые поля в LessioClient/Booking/Service/TutorProfile (см. Chunk 1.1)
- `app/lessio/service.py` — `register_tutor`, `create_services_from_template`, `find_free_slots` (реальная имплементация вместо stub)
- `app/main.py` — `app.include_router(web_router)` для нового
- `app/main.py` — расширить `/sitemap.xml` чтобы включать активные /u/<slug>
- `app/main.py` — `/robots.txt` явно разрешить `/u/`
- `tests/conftest.py` — уже импортирует `app.lessio.models`, ничего не меняем

---

## Chunk 1.1: Migration 0042 + models update

**Files:**
- Create: `alembic/versions/0042_lessio_web_expansion.py`
- Modify: `app/lessio/models.py`
- Test: `tests/test_lessio_web_models.py` (новый)

### Steps

- [ ] **Step 1: Написать failing-test для новых полей**

Create `tests/test_lessio_web_models.py`:

```python
"""Lessio models — поля для web-flow: email/phone в Client, magic-token + denorm в Booking."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import (
    LessioBooking,
    LessioClient,
    LessioService,
    LessioTutorProfile,
)


async def test_client_supports_anon_email_phone_name(db_session: AsyncSession) -> None:
    """Web-клиент создаётся БЕЗ telegram_user_id, с email/phone/full_name."""
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000001)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="test_t1", display_name="T1"
    )
    await db_session.commit()

    client = LessioClient(
        tutor_id=tutor.id,
        telegram_user_id=None,  # anon-web
        email="anon@example.com",
        phone="+79991234567",
        full_name="Anon Web",
    )
    db_session.add(client)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(LessioClient).where(LessioClient.email == "anon@example.com")
        )
    ).scalar_one()
    assert fetched.telegram_user_id is None
    assert fetched.phone == "+79991234567"
    assert fetched.full_name == "Anon Web"


async def test_booking_has_manage_token_and_denorm(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000002)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="test_t2", display_name="T2"
    )
    service = LessioService(
        tutor_id=tutor.id, title="Test", duration_minutes=60, price_kopecks=100000, price_stars=100
    )
    client = LessioClient(
        tutor_id=tutor.id, email="c@e.com", full_name="C", telegram_user_id=None
    )
    db_session.add_all([service, client])
    await db_session.commit()

    booking = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
        duration_minutes=60,
        price_kopecks=100000,
        price_stars=100,
        manage_token="a" * 64,
        payment_status="unpaid",
        client_email="c@e.com",
        client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(LessioBooking).where(LessioBooking.manage_token == "a" * 64)
        )
    ).scalar_one()
    assert fetched.payment_status == "unpaid"
    assert fetched.client_email == "c@e.com"
    assert fetched.reminder_24h_sent_at is None
    assert fetched.reminder_1h_sent_at is None


async def test_service_has_meeting_url_and_group_fields(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000003)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="test_t3", display_name="T3"
    )
    service = LessioService(
        tutor_id=tutor.id,
        title="Group Yoga",
        duration_minutes=60,
        price_kopecks=80000,
        price_stars=80,
        meeting_url_template="https://meet.jit.si/lessio-yoga",
        is_group_session=True,
        max_attendees=8,
        location="онлайн",
    )
    db_session.add(service)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(LessioService).where(LessioService.title == "Group Yoga")
        )
    ).scalar_one()
    assert fetched.is_group_session is True
    assert fetched.max_attendees == 8
    assert fetched.meeting_url_template.startswith("https://meet.jit.si")


async def test_tutor_profile_has_meeting_template_and_gc_token(db_session: AsyncSession) -> None:
    from app.lessio.service import auto_onboard_tutor, create_tutor_profile

    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=10000004)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="test_t4", display_name="T4"
    )
    tutor.default_meeting_url_template = "https://zoom.us/j/123"
    tutor.notification_email = "notify@example.com"
    tutor.google_calendar_refresh_token = "encrypted_token_blob"
    await db_session.commit()

    refetched = await db_session.get(LessioTutorProfile, tutor.id)
    assert refetched.default_meeting_url_template == "https://zoom.us/j/123"
    assert refetched.notification_email == "notify@example.com"
    assert refetched.google_calendar_refresh_token == "encrypted_token_blob"
```

- [ ] **Step 2: Run test, expect ImportError / AttributeError**

```bash
uv run pytest tests/test_lessio_web_models.py -v
```
Expected: FAIL — поля не существуют.

- [ ] **Step 3: Update models.py**

Modify `app/lessio/models.py`:

В `LessioClient`:
```python
class LessioClient(Base):
    __tablename__ = "lessio_clients"
    __table_args__ = (
        # Web-клиент уникален per-tutor по email; telegram_user_id остаётся
        # как partial unique для TG-only кейсов.
        UniqueConstraint("tutor_id", "email", name="uq_lessio_client_tutor_email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Telegram-only клиенты — telegram_user_id, web-only — email/phone/full_name.
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
```

В `LessioBooking`:
```python
class LessioBooking(Base):
    __tablename__ = "lessio_bookings"
    __table_args__ = (
        # Partial unique для индивидуальных встреч: для групповых одинаковый
        # starts_at допустим (несколько участников).
        # Postgres-only — alembic делает через op.execute.
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tutor_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_tutor_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("lessio_services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    price_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    price_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    star_payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("star_payments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # NEW в 0042:
    manage_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_24h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_1h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    client_full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

В `LessioService` — добавить `meeting_url_template`, `is_group_session`, `max_attendees`, `location`. В `LessioTutorProfile` — добавить `default_meeting_url_template`, `notification_email`, `google_calendar_refresh_token`. (Полная копия моделей в коде Chunk 1.1 — implementer берёт текущий models.py и расширяет.)

- [ ] **Step 4: Создать миграцию 0042**

Create `alembic/versions/0042_lessio_web_expansion.py`:

```python
"""Lessio web expansion — alter clients/bookings/services/tutor_profiles for web-flow.

Backward-compatible: все новые колонки nullable либо с server_default.
Partial-unique constraint на bookings (tutor_id, starts_at) для НЕ-групповых
встреч добавлен через op.execute (alembic-autogen не поддерживает partial-unique).

Revision ID: 0042
Revises: 0041
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── lessio_clients ────────────────────────────────────────────────────
    # telegram_user_id → nullable (web-клиенты без TG)
    op.alter_column(
        "lessio_clients", "telegram_user_id", existing_type=sa.BigInteger, nullable=True
    )
    op.add_column("lessio_clients", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("lessio_clients", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("lessio_clients", sa.Column("full_name", sa.String(120), nullable=True))
    # NB: backfill для существующих TG-клиентов (если есть в проде) — email из
    # placeholder. Пока в lessio_clients строк ноль, поэтому просто NOT NULL после backfill.
    op.execute(
        "UPDATE lessio_clients SET email='legacy_tg_' || telegram_user_id || '@placeholder.lessio', "
        "full_name=COALESCE(telegram_first_name, 'TG User') WHERE email IS NULL"
    )
    op.alter_column("lessio_clients", "email", existing_type=sa.String(255), nullable=False)
    op.alter_column("lessio_clients", "full_name", existing_type=sa.String(120), nullable=False)
    op.create_index("ix_lessio_clients_email", "lessio_clients", ["email"])
    op.create_unique_constraint(
        "uq_lessio_client_tutor_email", "lessio_clients", ["tutor_id", "email"]
    )

    # ── lessio_bookings ────────────────────────────────────────────────────
    op.add_column("lessio_bookings", sa.Column("manage_token", sa.String(64), nullable=True))
    op.add_column("lessio_bookings", sa.Column("meeting_url", sa.String(500), nullable=True))
    op.add_column(
        "lessio_bookings",
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="unpaid"),
    )
    op.add_column(
        "lessio_bookings", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "lessio_bookings",
        sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lessio_bookings",
        sa.Column("reminder_1h_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("lessio_bookings", sa.Column("client_email", sa.String(255), nullable=True))
    op.add_column("lessio_bookings", sa.Column("client_full_name", sa.String(120), nullable=True))
    # Backfill для существующих bookings (lessio_bookings пустой в проде, но safe).
    op.execute(
        "UPDATE lessio_bookings b SET "
        "manage_token=encode(gen_random_bytes(32), 'hex'), "
        "client_email=COALESCE((SELECT email FROM lessio_clients WHERE id=b.client_id), 'unknown@example.com'), "
        "client_full_name=COALESCE((SELECT full_name FROM lessio_clients WHERE id=b.client_id), 'Unknown') "
        "WHERE manage_token IS NULL"
    )
    op.alter_column(
        "lessio_bookings", "manage_token", existing_type=sa.String(64), nullable=False
    )
    op.alter_column(
        "lessio_bookings", "client_email", existing_type=sa.String(255), nullable=False
    )
    op.alter_column(
        "lessio_bookings", "client_full_name", existing_type=sa.String(120), nullable=False
    )
    op.create_unique_constraint(
        "uq_lessio_booking_manage_token", "lessio_bookings", ["manage_token"]
    )
    op.create_index(
        "ix_lessio_booking_manage_token", "lessio_bookings", ["manage_token"]
    )
    # Drop старый full unique (tutor_id, starts_at) — заменяем на partial unique.
    op.drop_constraint("uq_lessio_booking_slot", "lessio_bookings", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_lessio_booking_active_slot "
        "ON lessio_bookings (tutor_id, starts_at) "
        "WHERE status IN ('confirmed', 'completed') "
        "  AND service_id IN (SELECT id FROM lessio_services WHERE is_group_session = false)"
    )

    # ── lessio_services ───────────────────────────────────────────────────
    op.add_column(
        "lessio_services", sa.Column("meeting_url_template", sa.String(500), nullable=True)
    )
    op.add_column(
        "lessio_services",
        sa.Column("is_group_session", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "lessio_services",
        sa.Column("max_attendees", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column("lessio_services", sa.Column("location", sa.String(500), nullable=True))

    # ── lessio_tutor_profiles ─────────────────────────────────────────────
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("default_meeting_url_template", sa.String(500), nullable=True),
    )
    op.add_column(
        "lessio_tutor_profiles", sa.Column("notification_email", sa.String(255), nullable=True)
    )
    op.add_column(
        "lessio_tutor_profiles",
        sa.Column("google_calendar_refresh_token", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessio_tutor_profiles", "google_calendar_refresh_token")
    op.drop_column("lessio_tutor_profiles", "notification_email")
    op.drop_column("lessio_tutor_profiles", "default_meeting_url_template")
    op.drop_column("lessio_services", "location")
    op.drop_column("lessio_services", "max_attendees")
    op.drop_column("lessio_services", "is_group_session")
    op.drop_column("lessio_services", "meeting_url_template")
    op.execute("DROP INDEX IF EXISTS uq_lessio_booking_active_slot")
    op.create_unique_constraint(
        "uq_lessio_booking_slot", "lessio_bookings", ["tutor_id", "starts_at"]
    )
    op.drop_index("ix_lessio_booking_manage_token", "lessio_bookings")
    op.drop_constraint("uq_lessio_booking_manage_token", "lessio_bookings", type_="unique")
    op.drop_column("lessio_bookings", "client_full_name")
    op.drop_column("lessio_bookings", "client_email")
    op.drop_column("lessio_bookings", "reminder_1h_sent_at")
    op.drop_column("lessio_bookings", "reminder_24h_sent_at")
    op.drop_column("lessio_bookings", "paid_at")
    op.drop_column("lessio_bookings", "payment_status")
    op.drop_column("lessio_bookings", "meeting_url")
    op.drop_column("lessio_bookings", "manage_token")
    op.drop_constraint("uq_lessio_client_tutor_email", "lessio_clients", type_="unique")
    op.drop_index("ix_lessio_clients_email", "lessio_clients")
    op.drop_column("lessio_clients", "full_name")
    op.drop_column("lessio_clients", "phone")
    op.drop_column("lessio_clients", "email")
    op.alter_column(
        "lessio_clients", "telegram_user_id", existing_type=sa.BigInteger, nullable=False
    )
```

- [ ] **Step 5: Применить миграцию (юзер делает локально)**

```bash
uv run alembic upgrade head
```
Expected: `Running upgrade 0041 -> 0042, lessio_web_expansion`

- [ ] **Step 6: Run test, ожидаем PASS**

```bash
uv run pytest tests/test_lessio_web_models.py -v
```
Expected: 4 passed.

- [ ] **Step 7: Полный test suite + lint**

```bash
uv run ruff check
uv run mypy --strict app/ scripts/
uv run pytest -q
```
Expected: всё зелёное. Существующие lessio-тесты могут потребовать adjustment (LessioBooking constructor теперь требует `manage_token` + `client_email` + `client_full_name`). Fix inline в существующих тестах.

- [ ] **Step 8: Commit**

```bash
git add -A
git -c user.name='SwairIt' -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "lessio migration 0042: web-expansion полей в clients/bookings/services/tutor_profiles + partial-unique для групповых"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Chunk 1.2: service.py — реальный find_free_slots + register_tutor + create_services_from_template

**Files:**
- Modify: `app/lessio/service.py`
- Test: `tests/test_lessio_web_free_slots.py` (новый)

### Steps

- [ ] **Step 1: Failing-test для find_free_slots**

Create `tests/test_lessio_web_free_slots.py`:

```python
"""find_free_slots алгоритм — granular cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioService
from app.lessio.service import (
    auto_onboard_tutor,
    create_tutor_profile,
    find_free_slots,
)


async def _setup_tutor(session: AsyncSession, *, tg_id: int = 20000001):
    user, _ = await auto_onboard_tutor(session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(
        session, user=user, slug=f"tutor_{tg_id}", display_name="T"
    )
    # Default: working_days=[1,2,3,4,5] (Mon-Fri), 9:00-21:00, buffer 15m
    return tutor


async def _add_service(session, tutor, *, duration_minutes: int = 60):
    service = LessioService(
        tutor_id=tutor.id,
        title="60min",
        duration_minutes=duration_minutes,
        price_kopecks=100000,
        price_stars=100,
    )
    session.add(service)
    await session.flush()
    return service


async def test_no_bookings_returns_all_slots(db_session: AsyncSession) -> None:
    """Без booked-времён — все слоты в working_hours свободны."""
    tutor = await _setup_tutor(db_session)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    # Понедельник 2026-06-01 — рабочий день. 9:00-21:00 = 12 часов = 12 слотов по 60м + 15м buffer.
    # С buffer = (60+15) = 75min spacing → fits 9 слотов от 9:00 до 21:00 (9:00, 10:15, 11:30, ...)
    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=1), service=service
    )
    assert len(slots) >= 8  # точное число зависит от рассчёта buffer'а


async def test_weekend_returns_empty(db_session: AsyncSession) -> None:
    """working_days=[1..5] не включает Sun=7, Sat=6."""
    tutor = await _setup_tutor(db_session, tg_id=20000002)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    saturday = datetime(2026, 6, 6, 0, 0, tzinfo=UTC)  # Sat
    slots = await find_free_slots(
        db_session, tutor, date_from=saturday, date_to=saturday + timedelta(days=1), service=service
    )
    assert slots == []


async def test_existing_booking_blocks_slot(db_session: AsyncSession) -> None:
    """Если slot занят — он не возвращается."""
    from app.lessio.models import LessioClient

    tutor = await _setup_tutor(db_session, tg_id=20000003)
    service = await _add_service(db_session, tutor)
    client = LessioClient(
        tutor_id=tutor.id, email="c@e.com", full_name="C", telegram_user_id=None
    )
    db_session.add(client)
    await db_session.flush()

    # Бронируем 10:00 в понедельник.
    booked_slot = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    booking = LessioBooking(
        tutor_id=tutor.id, client_id=client.id, service_id=service.id,
        starts_at=booked_slot, duration_minutes=60, status="confirmed",
        price_kopecks=100000, price_stars=100,
        manage_token="t" * 64, payment_status="unpaid",
        client_email="c@e.com", client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=1), service=service
    )
    assert booked_slot not in slots


async def test_cancelled_booking_does_not_block(db_session: AsyncSession) -> None:
    """status='cancelled' — слот снова свободен."""
    from app.lessio.models import LessioClient

    tutor = await _setup_tutor(db_session, tg_id=20000004)
    service = await _add_service(db_session, tutor)
    client = LessioClient(
        tutor_id=tutor.id, email="c@e.com", full_name="C", telegram_user_id=None
    )
    db_session.add(client)
    await db_session.flush()

    cancelled = LessioBooking(
        tutor_id=tutor.id, client_id=client.id, service_id=service.id,
        starts_at=datetime(2026, 6, 1, 11, 0, tzinfo=UTC),
        duration_minutes=60, status="cancelled",
        price_kopecks=100000, price_stars=100,
        manage_token="x" * 64, payment_status="refunded",
        client_email="c@e.com", client_full_name="C",
    )
    db_session.add(cancelled)
    await db_session.commit()

    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=1), service=service
    )
    assert any(s.hour == 11 for s in slots)


async def test_buffer_respected(db_session: AsyncSession) -> None:
    """Buffer 15 минут — после 10:00 (длительность 60м) следующий слот не раньше 11:15."""
    from app.lessio.models import LessioClient

    tutor = await _setup_tutor(db_session, tg_id=20000005)
    service = await _add_service(db_session, tutor, duration_minutes=60)
    client = LessioClient(
        tutor_id=tutor.id, email="c@e.com", full_name="C", telegram_user_id=None
    )
    db_session.add(client)
    await db_session.flush()

    booking = LessioBooking(
        tutor_id=tutor.id, client_id=client.id, service_id=service.id,
        starts_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        duration_minutes=60, status="confirmed",
        price_kopecks=100000, price_stars=100,
        manage_token="b" * 64, payment_status="unpaid",
        client_email="c@e.com", client_full_name="C",
    )
    db_session.add(booking)
    await db_session.commit()

    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=1), service=service
    )
    after_booking = [s for s in slots if s.hour >= 10]
    # 11:00 не должно быть (10:00 + 60min = 11:00, + 15min buffer = 11:15)
    assert datetime(2026, 6, 1, 11, 0, tzinfo=UTC) not in after_booking


async def test_past_slots_excluded(db_session: AsyncSession) -> None:
    """Слоты в прошлом не возвращаются даже если попадают в date_from."""
    tutor = await _setup_tutor(db_session, tg_id=20000006)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    # date_from в прошлом
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    slots = await find_free_slots(
        db_session, tutor, date_from=yesterday, date_to=now, service=service
    )
    for s in slots:
        assert s >= now


async def test_group_service_allows_multiple_at_same_slot(db_session: AsyncSession) -> None:
    """is_group_session=True — slot не блокируется одним booking'ом если max_attendees > 1."""
    from app.lessio.models import LessioClient

    tutor = await _setup_tutor(db_session, tg_id=20000007)
    service = LessioService(
        tutor_id=tutor.id, title="Yoga group", duration_minutes=60,
        price_kopecks=80000, price_stars=80,
        is_group_session=True, max_attendees=8,
    )
    db_session.add(service)
    await db_session.flush()

    client = LessioClient(
        tutor_id=tutor.id, email="c@e.com", full_name="C", telegram_user_id=None
    )
    db_session.add(client)
    await db_session.flush()

    # 7 уже записаны
    for i in range(7):
        b = LessioBooking(
            tutor_id=tutor.id, client_id=client.id, service_id=service.id,
            starts_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            duration_minutes=60, status="confirmed",
            price_kopecks=80000, price_stars=80,
            manage_token=f"g{i}" * 32, payment_status="unpaid",
            client_email="c@e.com", client_full_name="C",
        )
        db_session.add(b)
    await db_session.commit()

    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=1), service=service
    )
    # 12:00 ещё свободен (7/8)
    assert datetime(2026, 6, 1, 12, 0, tzinfo=UTC) in slots


async def test_returns_sorted_slots(db_session: AsyncSession) -> None:
    """Слоты возвращаются в хронологическом порядке."""
    tutor = await _setup_tutor(db_session, tg_id=20000008)
    service = await _add_service(db_session, tutor)
    await db_session.commit()

    monday = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    slots = await find_free_slots(
        db_session, tutor, date_from=monday, date_to=monday + timedelta(days=7), service=service
    )
    for i in range(len(slots) - 1):
        assert slots[i] < slots[i + 1]
```

- [ ] **Step 2: Run test, expect FAIL (find_free_slots stub возвращает [])**

```bash
uv run pytest tests/test_lessio_web_free_slots.py -v
```
Expected: FAIL — current stub returns empty list.

- [ ] **Step 3: Implement find_free_slots real**

Modify `app/lessio/service.py` — заменить stub:

```python
async def find_free_slots(
    session: AsyncSession,
    tutor: LessioTutorProfile,
    *,
    date_from: datetime,
    date_to: datetime,
    service: LessioService,
) -> list[datetime]:
    """Compute free slots в [date_from, date_to) для услуги.

    Алгоритм:
    1. Для каждого дня в [date_from, date_to):
       - Skip если weekday не в tutor.working_days
       - Перебор start_minute от tutor.work_start_minute до work_end_minute
         с шагом (service.duration_minutes + tutor.buffer_minutes)
       - Не выходить за work_end_minute
    2. Subtract existing bookings:
       - Для индивидуальной услуги (is_group_session=False): любой confirmed booking
         на (tutor_id, starts_at) блокирует слот + buffer вокруг него
       - Для group session: блокируется когда max_attendees достигнут
    3. Skip past slots (slot < now())
    """
    from sqlalchemy import and_, func, select

    now = datetime.now(UTC)
    floor_dt = max(date_from, now)

    # 1. Generate candidate slots
    candidates: list[datetime] = []
    day = floor_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if day < floor_dt:
        day += timedelta(days=1)  # начать с следующего дня если уже за полночь
    # Wait — нет, начать с floor_dt самого
    day = floor_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    working_days = set(tutor.working_days)  # 1=Mon..7=Sun
    step = service.duration_minutes + tutor.buffer_minutes

    while day < date_to:
        weekday = day.isoweekday()
        if weekday in working_days:
            minute = tutor.work_start_minute
            while minute + service.duration_minutes <= tutor.work_end_minute:
                slot = day + timedelta(minutes=minute)
                if slot >= now:
                    candidates.append(slot)
                minute += step
        day += timedelta(days=1)

    if not candidates:
        return []

    # 2. Subtract busy slots
    bookings = (
        await session.execute(
            select(LessioBooking)
            .where(
                and_(
                    LessioBooking.tutor_id == tutor.id,
                    LessioBooking.status.in_(["confirmed", "completed"]),
                    LessioBooking.starts_at >= candidates[0] - timedelta(hours=24),
                    LessioBooking.starts_at <= candidates[-1] + timedelta(hours=24),
                )
            )
        )
    ).scalars().all()

    # Build busy set per starts_at considering buffer
    busy_intervals: list[tuple[datetime, datetime]] = []
    group_counts: dict[datetime, int] = {}
    for b in bookings:
        end_with_buffer = b.starts_at + timedelta(
            minutes=b.duration_minutes + tutor.buffer_minutes
        )
        start_with_buffer = b.starts_at - timedelta(minutes=tutor.buffer_minutes)
        if service.is_group_session and b.service_id == service.id:
            group_counts[b.starts_at] = group_counts.get(b.starts_at, 0) + 1
        else:
            busy_intervals.append((start_with_buffer, end_with_buffer))

    def is_free(slot: datetime) -> bool:
        # 1. Group session: slot свободен пока attendees < max
        if service.is_group_session:
            return group_counts.get(slot, 0) < service.max_attendees
        # 2. Individual: slot не должен пересекать busy interval
        slot_end = slot + timedelta(minutes=service.duration_minutes)
        for busy_start, busy_end in busy_intervals:
            if slot < busy_end and slot_end > busy_start:
                return False
        return True

    return sorted([s for s in candidates if is_free(s)])
```

- [ ] **Step 4: Run test, expect PASS**

```bash
uv run pytest tests/test_lessio_web_free_slots.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Add register_tutor + create_services_from_template**

Append to `app/lessio/service.py`:

```python
# ── Web-flow regishtration ────────────────────────────────────────────

_SERVICE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "english": [
        {"title": "Английский · урок 60 мин", "duration_minutes": 60, "price_kopecks": 150000, "price_stars": 1500},
        {"title": "Английский · пакет 4 урока", "duration_minutes": 60, "price_kopecks": 540000, "price_stars": 5400, "package_size": 4},
    ],
    "ielts": [
        {"title": "IELTS подготовка · 90 мин", "duration_minutes": 90, "price_kopecks": 250000, "price_stars": 2500},
        {"title": "Mock IELTS Speaking", "duration_minutes": 30, "price_kopecks": 100000, "price_stars": 1000},
    ],
    "math": [
        {"title": "Математика · 60 мин", "duration_minutes": 60, "price_kopecks": 120000, "price_stars": 1200},
    ],
    "school": [
        {"title": "ЕГЭ профильный — 60 мин", "duration_minutes": 60, "price_kopecks": 180000, "price_stars": 1800},
    ],
    "fitness": [
        {"title": "Персональная тренировка 60 мин", "duration_minutes": 60, "price_kopecks": 200000, "price_stars": 2000},
    ],
    "psychology": [
        {"title": "Консультация 50 мин", "duration_minutes": 50, "price_kopecks": 350000, "price_stars": 3500},
    ],
    "yoga": [
        {
            "title": "Групповая йога 60 мин",
            "duration_minutes": 60,
            "price_kopecks": 80000,
            "price_stars": 800,
            "is_group_session": True,
            "max_attendees": 8,
        },
    ],
    "other": [
        {"title": "Встреча 60 мин", "duration_minutes": 60, "price_kopecks": 150000, "price_stars": 1500},
    ],
}


async def create_services_from_template(
    session: AsyncSession,
    *,
    tutor: LessioTutorProfile,
    niche: str,
) -> list[LessioService]:
    """Bulk-create default-услуг под нишу tutor'а."""
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
```

- [ ] **Step 6: Run lint+types+full test**

```bash
uv run ruff check && uv run mypy --strict app/ scripts/ && uv run pytest -q
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add -A
git -c user.name='SwairIt' -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "lessio service.py: реальный find_free_slots (working_days+buffer+group) + service templates"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Chunk 1.3: Web register + setup-profile flow

**Files:**
- Create: `app/lessio/web_router.py`
- Create: `app/templates/lessio/auth/lessio_register.html`
- Create: `app/templates/lessio/app/setup_profile.html`
- Modify: `app/main.py` (include web_router)
- Test: `tests/test_lessio_web_register.py`

### Steps

- [ ] **Step 1: Failing-test для register → setup-profile flow**

Create `tests/test_lessio_web_register.py`:

```python
"""Lessio web register-flow: /lessio/auth/register → /lessio/app/setup-profile → profile создан."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.lessio.models import LessioService, LessioTutorProfile


async def test_register_page_renders(client: AsyncClient) -> None:
    resp = await client.get("/lessio/auth/register")
    assert resp.status_code == 200
    body = resp.text
    assert "Регистрация" in body or "регистрация" in body.lower()
    assert "name=\"email\"" in body
    assert "name=\"password\"" in body


async def test_register_creates_user_and_redirects_to_setup(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/lessio/auth/register",
        data={"email": "tutor1@example.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/lessio/app/setup-profile" in resp.headers["location"]

    user = (
        await db_session.execute(select(User).where(User.email == "tutor1@example.com"))
    ).scalar_one_or_none()
    assert user is not None
    assert user.password_hash is not None  # email+password, не TG-only


async def test_setup_profile_creates_tutor_and_services(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1) Register
    await client.post(
        "/lessio/auth/register",
        data={"email": "tutor2@example.com", "password": "strongpass123"},
    )
    # 2) Submit setup-profile form
    resp = await client.post(
        "/lessio/app/setup-profile",
        data={
            "slug": "anna_eng",
            "display_name": "Anna · English",
            "niche": "english",
            "bio": "5 лет опыта",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"].endswith("/lessio/app/today")

    # 3) Verify created
    profile = (
        await db_session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == "anna_eng")
        )
    ).scalar_one()
    assert profile.display_name == "Anna · English"

    services = (
        await db_session.execute(
            select(LessioService).where(LessioService.tutor_id == profile.id)
        )
    ).scalars().all()
    assert len(services) >= 1  # default templates created
    assert any("Английский" in s.title for s in services)


async def test_setup_profile_rejects_duplicate_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1st tutor
    await client.post(
        "/lessio/auth/register", data={"email": "t3@e.com", "password": "p" * 12}
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "popular", "display_name": "First", "niche": "english"},
    )
    # 2nd tutor with same slug → 400
    await client.post(
        "/lessio/auth/register", data={"email": "t4@e.com", "password": "p" * 12}
    )
    resp = await client.post(
        "/lessio/app/setup-profile",
        data={"slug": "popular", "display_name": "Second", "niche": "english"},
    )
    assert resp.status_code == 400
    assert "занят" in resp.text
```

- [ ] **Step 2: Run, expect 404 на /lessio/auth/register**

```bash
uv run pytest tests/test_lessio_web_register.py -v
```
Expected: FAIL — endpoints не существуют.

- [ ] **Step 3: Создать web_router.py**

Create `app/lessio/web_router.py`:

```python
"""Lessio web router — register/login + setup-profile + cabinet shell.

Отдельно от существующего app.lessio.router (он держит landing + waitlist +
Mini App endpoints). Этот модуль — для веб-кабинета через стандартный
Doday-auth (email+password).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, DbSession, RequiredUser
from app.auth.schemas import RegisterIn
from app.auth.service import EmailAlreadyExists, register_user
from app.db import get_session
from app.lessio.models import LessioTutorProfile
from app.lessio.service import (
    OnboardError,
    create_services_from_template,
    create_tutor_profile,
)

router = APIRouter(prefix="/lessio", tags=["lessio-web"])
_templates = Jinja2Templates(directory="app/templates")


_ALLOWED_NICHES: frozenset[str] = frozenset(
    {"english", "ielts", "math", "school", "fitness", "psychology", "yoga", "other"}
)


# ── Auth ────────────────────────────────────────────────────────────


@router.get("/auth/register", response_class=HTMLResponse, include_in_schema=False)
async def lessio_register_page(request: Request, user: CurrentUser) -> Response:
    if user is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)
    return _templates.TemplateResponse(request, "lessio/auth/lessio_register.html", {})


@router.post("/auth/register", response_class=HTMLResponse, include_in_schema=False)
async def lessio_register_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    if len(password) < 8:
        return _templates.TemplateResponse(
            request,
            "lessio/auth/lessio_register.html",
            {"error": "Пароль минимум 8 символов"},
            status_code=400,
        )
    try:
        user = await register_user(
            session, RegisterIn(email=email.lower().strip(), password=password)
        )
    except EmailAlreadyExists:
        return _templates.TemplateResponse(
            request,
            "lessio/auth/lessio_register.html",
            {"error": "Email уже зарегистрирован — войдите через /lessio/auth/login"},
            status_code=400,
        )

    # Auto-login через session-cookie. Используем тот же механизм что в /auth/login.
    request.session["user_id"] = str(user.id)
    return RedirectResponse("/lessio/app/setup-profile", status_code=303)


# ── Setup-profile ─────────────────────────────────────────────────────


@router.get("/app/setup-profile", response_class=HTMLResponse, include_in_schema=False)
async def setup_profile_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    existing = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)
    return _templates.TemplateResponse(request, "lessio/app/setup_profile.html", {})


@router.post("/app/setup-profile", response_class=HTMLResponse, include_in_schema=False)
async def setup_profile_submit(
    request: Request,
    user: RequiredUser,
    slug: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    niche: Annotated[str, Form()],
    bio: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    existing = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse("/lessio/app/today", status_code=302)

    safe_niche = niche if niche in _ALLOWED_NICHES else "other"
    try:
        tutor = await create_tutor_profile(
            session,
            user=user,
            slug=slug,
            display_name=display_name,
            niche=safe_niche,
            bio=bio,
        )
    except OnboardError as exc:
        return _templates.TemplateResponse(
            request,
            "lessio/app/setup_profile.html",
            {"error": str(exc), "slug": slug, "display_name": display_name, "bio": bio},
            status_code=400,
        )

    await create_services_from_template(session, tutor=tutor, niche=safe_niche)
    await session.commit()
    return RedirectResponse("/lessio/app/today", status_code=302)


# ── Placeholder cabinet endpoint ──────────────────────────────────────


@router.get("/app/today", response_class=HTMLResponse, include_in_schema=False)
async def lessio_today_placeholder(user: RequiredUser, session: DbSession) -> Response:
    """Минимальный today-page. Полный — chunk 3.2 (week 3)."""
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return RedirectResponse("/lessio/app/setup-profile", status_code=302)
    return HTMLResponse(
        f'<!doctype html><meta charset="utf-8"><title>Lessio · {profile.display_name}</title>'
        '<body style="font-family:sans-serif;background:#0f0a1f;color:#f5f3ff;padding:2em;">'
        f"<h1>Привет, {profile.display_name}!</h1>"
        f'<p>Твоя публичная ссылка: <a href="/u/{profile.slug}" '
        f'style="color:#a78bfa">getdoday.ru/u/{profile.slug}</a></p>'
        '<p style="color:#a78bfa">Кабинет (Today/Calendar/Clients/...) — в разработке.</p>'
        "</body>"
    )
```

- [ ] **Step 4: Create templates**

Create `app/templates/lessio/auth/lessio_register.html`:

```html
{% extends "lessio/_base_auth.html" %}
{% block title %}Регистрация репетитора · Lessio{% endblock %}
{% block content %}
<div class="mx-auto max-w-md py-12 px-5">
  <h1 class="text-3xl font-extrabold mb-2">Стать репетитором</h1>
  <p class="text-violet-200/70 mb-6">5 секунд: email + пароль. Дальше — настройка профиля.</p>
  {% if error %}
  <div class="mb-4 px-4 py-3 rounded-xl bg-rose-500/15 text-rose-300">{{ error }}</div>
  {% endif %}
  <form method="post" action="/lessio/auth/register" class="space-y-3">
    <input name="email" type="email" required placeholder="email"
           class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl">
    <input name="password" type="password" required minlength="8" placeholder="пароль (≥8 символов)"
           class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl">
    <button class="w-full px-6 py-3.5 bg-gradient-to-r from-violet-500 to-pink-500 rounded-xl font-bold">
      Создать аккаунт →
    </button>
  </form>
  <p class="text-center text-sm text-violet-300/50 mt-6">
    Уже есть аккаунт? <a href="/lessio/auth/login" class="underline">Войти</a>
  </p>
</div>
{% endblock %}
```

Create `app/templates/lessio/_base_auth.html` (shared auth shell):

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}Lessio{% endblock %}</title>
  <meta name="robots" content="noindex,nofollow">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background: linear-gradient(180deg, #0f0a1f 0%, #1a0f3d 60%, #2e1065 100%);
           color: #f5f3ff; min-height: 100vh;
           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  </style>
</head>
<body>{% block content %}{% endblock %}</body>
</html>
```

Create `app/templates/lessio/app/setup_profile.html`:

```html
{% extends "lessio/_base_auth.html" %}
{% block title %}Настройка профиля · Lessio{% endblock %}
{% block content %}
<div class="mx-auto max-w-xl py-12 px-5">
  <h1 class="text-3xl font-extrabold mb-2">Настроим профиль</h1>
  <p class="text-violet-200/70 mb-6">30 секунд. Эти данные увидят клиенты на твоей публичной странице.</p>
  {% if error %}<div class="mb-4 px-4 py-3 rounded-xl bg-rose-500/15 text-rose-300">{{ error }}</div>{% endif %}

  <form method="post" action="/lessio/app/setup-profile" class="space-y-5
        bg-white/5 border border-white/10 rounded-2xl p-5">
    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Публичная ссылка</span>
      <div class="flex items-center gap-2">
        <span class="text-violet-300/60 text-sm">getdoday.ru/u/</span>
        <input name="slug" type="text" required minlength="3" maxlength="50"
               pattern="[a-z0-9][a-z0-9_-]{2,49}" placeholder="anna_english"
               value="{{ slug or '' }}"
               class="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg">
      </div>
    </label>
    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Имя на странице</span>
      <input name="display_name" type="text" required maxlength="100"
             placeholder="Анна · английский для взрослых" value="{{ display_name or '' }}"
             class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg">
    </label>
    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Что преподаёшь</span>
      <select name="niche" class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg">
        <option value="english">Английский / иностранные языки</option>
        <option value="ielts">IELTS / TOEFL / экзамены</option>
        <option value="math">Математика / физика / другие предметы</option>
        <option value="school">Школа / ЕГЭ / ОГЭ</option>
        <option value="fitness">Фитнес / йога / тренер</option>
        <option value="psychology">Психология / коучинг</option>
        <option value="yoga">Йога / медитация</option>
        <option value="other">Что-то другое</option>
      </select>
    </label>
    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">О себе (опционально)</span>
      <textarea name="bio" rows="3" maxlength="1000" placeholder="5 лет опыта, IELTS 8.0..."
                class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg resize-none">{{ bio or '' }}</textarea>
    </label>
    <button class="w-full px-6 py-3.5 bg-gradient-to-r from-violet-500 to-pink-500 rounded-xl font-bold">
      Создать профиль и сгенерировать услуги →
    </button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Register router in main.py**

Modify `app/main.py`:

```python
from app.lessio.web_router import router as lessio_web_router
# ...
app.include_router(lessio_web_router)
```

- [ ] **Step 6: Add per-file-ignores в pyproject**

Add line:
```toml
"app/lessio/web_router.py" = ["RUF001", "RUF002", "RUF003"]
```

- [ ] **Step 7: Run all checks**

```bash
uv run ruff check && uv run mypy --strict app/ scripts/ && uv run pytest tests/test_lessio_web_register.py -v
```
Expected: 4 passed.

- [ ] **Step 8: Commit + push**

```bash
git add -A
git -c user.name='SwairIt' -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "lessio web register-flow: /lessio/auth/register + /lessio/app/setup-profile + default-услуги"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Chunk 1.4: Public profile `/u/<slug>` + базовый SEO

**Files:**
- Modify: `app/lessio/web_router.py` — add `/u/<slug>` handler
- Create: `app/templates/lessio/u/profile.html`
- Modify: `app/main.py` — sitemap include `/u/<slug>` для активных профилей
- Modify: `app/main.py` — robots.txt allow `/u/`
- Test: `tests/test_lessio_web_public_profile.py`

### Steps

- [ ] **Step 1: Failing-test**

Create `tests/test_lessio_web_public_profile.py`:

```python
"""Public profile /u/<slug> — render + SEO meta + 404."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.service import (
    auto_onboard_tutor,
    create_services_from_template,
    create_tutor_profile,
)


async def test_unknown_slug_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/u/nonexistent")
    assert resp.status_code == 404


async def test_public_profile_renders_with_services(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000001)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="anna_eng", display_name="Anna · English",
        niche="english", bio="5 лет опыта"
    )
    await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    resp = await client.get("/u/anna_eng")
    assert resp.status_code == 200
    body = resp.text
    assert "Anna · English" in body
    assert "5 лет опыта" in body
    assert "Английский" in body  # service title from template


async def test_public_profile_has_seo_meta(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000002)
    await create_tutor_profile(
        db_session, user=user, slug="seo_test", display_name="SEO Tutor",
        niche="english", bio="testing seo"
    )
    await db_session.commit()

    resp = await client.get("/u/seo_test")
    body = resp.text
    # canonical URL
    assert '<link rel="canonical" href="https://getdoday.ru/u/seo_test"' in body
    # OG-tags
    assert 'property="og:title"' in body
    assert 'property="og:url"' in body
    assert 'content="https://getdoday.ru/u/seo_test"' in body
    # JSON-LD Person schema
    assert "application/ld+json" in body
    assert '"@type": "Person"' in body or '"@type":"Person"' in body
    assert "SEO Tutor" in body


async def test_inactive_profile_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=30000003)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="inactive_one", display_name="Inactive"
    )
    tutor.is_active = False
    await db_session.commit()

    resp = await client.get("/u/inactive_one")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/test_lessio_web_public_profile.py -v
```

- [ ] **Step 3: Implement /u/<slug> handler**

Add to `app/lessio/web_router.py`:

```python
from app.lessio.models import LessioService

_public_router = APIRouter(tags=["lessio-public"])


@_public_router.get("/u/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def public_profile(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
        )
    ).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")

    services = (
        await session.execute(
            select(LessioService)
            .where(LessioService.tutor_id == profile.id, LessioService.is_active == True)
            .order_by(LessioService.price_kopecks)
        )
    ).scalars().all()

    return _templates.TemplateResponse(
        request,
        "lessio/u/profile.html",
        {
            "tutor": profile,
            "services": services,
            "canonical_url": f"https://getdoday.ru/u/{profile.slug}",
        },
    )
```

И в нижней части файла:
```python
# Re-export both routers — main.py подключит оба.
public_router = _public_router
```

Update `app/main.py`:
```python
from app.lessio.web_router import public_router as lessio_public_router
from app.lessio.web_router import router as lessio_web_router
app.include_router(lessio_web_router)
app.include_router(lessio_public_router)
```

- [ ] **Step 4: Create profile.html template**

Create `app/templates/lessio/u/profile.html`:

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ tutor.display_name }} · Lessio</title>
  <meta name="description"
        content="{{ tutor.display_name }} — записаться на занятие через Lessio. {{ tutor.bio[:150] if tutor.bio else '' }}">
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="{{ canonical_url }}">

  <meta property="og:type" content="profile">
  <meta property="og:title" content="{{ tutor.display_name }} · Lessio">
  <meta property="og:description" content="{{ tutor.bio[:150] if tutor.bio else 'Запись на занятие через Lessio' }}">
  <meta property="og:url" content="{{ canonical_url }}">
  <meta property="og:image" content="https://getdoday.ru/og.svg">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{{ tutor.display_name }} · Lessio">

  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "{{ tutor.display_name }}",
    "url": "{{ canonical_url }}",
    "description": "{{ tutor.bio[:300] if tutor.bio else '' }}",
    "jobTitle": "{{ {'english': 'Преподаватель английского', 'math': 'Репетитор математики', 'fitness': 'Тренер', 'psychology': 'Психолог', 'yoga': 'Инструктор йоги'}.get(tutor.niche, 'Преподаватель') }}",
    "makesOffer": [
      {% for s in services %}
      {
        "@type": "Offer",
        "name": "{{ s.title }}",
        "price": "{{ s.price_kopecks // 100 }}",
        "priceCurrency": "RUB"
      }{% if not loop.last %},{% endif %}
      {% endfor %}
    ]
  }
  </script>

  <link rel="icon" href="/favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background: linear-gradient(180deg, #0f0a1f 0%, #1a0f3d 60%, #2e1065 100%);
           color: #f5f3ff; min-height: 100vh;
           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .gradient-text { background: linear-gradient(135deg, #a78bfa, #f472b6);
                     -webkit-background-clip: text; background-clip: text; color: transparent; }
  </style>
</head>
<body class="antialiased">
<main class="mx-auto max-w-3xl px-5 py-12">

  <header class="text-center mb-12">
    <div class="text-6xl mb-4">{{ tutor.avatar_emoji }}</div>
    <h1 class="text-4xl font-extrabold mb-3 gradient-text">{{ tutor.display_name }}</h1>
    {% if tutor.bio %}
    <p class="text-violet-200/80 leading-relaxed max-w-xl mx-auto">{{ tutor.bio }}</p>
    {% endif %}
  </header>

  <section>
    <h2 class="text-xl font-bold mb-5 text-violet-200/70">Доступные услуги</h2>
    <div class="grid sm:grid-cols-2 gap-4">
      {% for s in services %}
      <a href="/u/{{ tutor.slug }}/book/{{ s.id }}"
         class="block bg-white/5 border border-white/10 rounded-2xl p-5 hover:border-violet-400/50 transition">
        <h3 class="font-bold text-lg mb-1">{{ s.title }}</h3>
        <p class="text-sm text-violet-300/70 mb-3">{{ s.duration_minutes }} мин
          {% if s.is_group_session %}· группа до {{ s.max_attendees }}{% endif %}
        </p>
        <div class="text-2xl font-extrabold">{{ "{:,}".format(s.price_kopecks // 100).replace(',', ' ') }} ₽</div>
        <div class="mt-3 text-sm text-violet-300/60">Записаться →</div>
      </a>
      {% else %}
      <p class="text-violet-300/50 col-span-2">У репетитора пока нет настроенных услуг.</p>
      {% endfor %}
    </div>
  </section>

  <footer class="text-center text-sm text-violet-300/50 mt-16 pt-8 border-t border-white/5">
    <p>Powered by <a href="/lessio" class="underline">Lessio</a> · часть <a href="/" class="underline">Doday Studio</a></p>
  </footer>
</main>
</body>
</html>
```

- [ ] **Step 5: Sitemap + robots updates**

Modify `app/main.py` `sitemap_xml()` function — добавить динамические `/u/<slug>`:

```python
@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.help.articles import ARTICLES
    from app.lessio.models import LessioTutorProfile

    base = _settings.app_base_url.rstrip("/")
    static_paths = [
        "/", "/doday", "/lessio",
        "/for-students", "/for-teachers", "/todoist-alternative",
        "/pricing", "/changelog", "/roadmap", "/help",
        "/privacy", "/terms",
    ]
    article_paths = [f"/help/{a['slug']}" for a in ARTICLES]

    # Lessio tutor public pages
    active_tutors = (
        await session.execute(
            select(LessioTutorProfile.slug).where(LessioTutorProfile.is_active == True)
        )
    ).scalars().all()
    tutor_paths = [f"/u/{slug}" for slug in active_tutors]

    items = "".join(
        f"<url><loc>{base}{p}</loc><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if p == '/' else '0.7'}</priority></url>"
        for p in static_paths + article_paths + tutor_paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return Response(content=body, media_type="application/xml")
```

В `robots_txt()` — добавить explicit Allow:

```python
body = (
    "User-agent: *\n"
    "Disallow: /app/\n"
    "Disallow: /api/\n"
    "Disallow: /htmx/\n"
    "Disallow: /auth/\n"
    "Disallow: /lessio/app/\n"
    "Disallow: /lessio/auth/\n"
    "Disallow: /lessio/manage/\n"
    "Allow: /u/\n"
    "Allow: /lessio$\n"
    f"Sitemap: {_settings.app_base_url.rstrip('/')}/sitemap.xml\n"
)
```

- [ ] **Step 6: Per-file-ignores для profile.html parsing (если будет ругаться lint_templates)**

Не нужно ничего — Jinja2 lint справится.

- [ ] **Step 7: Run all tests**

```bash
uv run ruff check && uv run mypy --strict app/ scripts/ && uv run pytest -q
```
Expected: green. Возможно sitemap test (test_seo_pages_and_invite) станет требовать `db_session` параметр — fix inline (передаём mock или live session).

- [ ] **Step 8: Smoke prod после deploy**

После push + cron-poll:
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://getdoday.ru/u/anna_eng  # 404 если нет такого slug
curl -s https://getdoday.ru/sitemap.xml | grep -c "/u/"  # должен быть >=0
```

- [ ] **Step 9: Commit + push**

```bash
git add -A
git -c user.name='SwairIt' -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "lessio public profile /u/<slug>: JSON-LD Person + OG + sitemap dynamic + robots allow /u/"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Week 1 — выход и переход к Week 2

После 4 chunks недели 1:
- ✅ Migration 0042 применена
- ✅ Полная регистрация репетитора через email+password
- ✅ Автогенерация default-услуг под нишу
- ✅ Публичная страница `/u/<slug>` с SEO (JSON-LD Person schema, OG-tags, canonical, в sitemap)
- ✅ Real `find_free_slots` (working_days + work_hours + buffer + existing bookings + group sessions)
- ✅ Robots.txt разрешает `/u/`
- ✅ Placeholder `/lessio/app/today` чтобы flow работал end-to-end

**Что НЕ делает Week 1:**
- Booking submit (форма + email) — Week 2
- Magic-link manage — Week 2
- Reminders cron — Week 2
- Полный cabinet (calendar/clients/services CRUD/income/settings) — Week 3
- Google Calendar OAuth — Week 3
- Dynamic OG-image per tutor (генерация SVG с именем) — SEO chunk Week 3

**После commit'а последнего chunk'а Week 1 → создать следующий plan-файл `2026-05-25-lessio-web-mvp-week2.md`** аналогичной структуры.

---

## Self-review

**Spec coverage** (gaps vs spec):
- ✅ Модели расширены (Chunk 1.1)
- ✅ Onboarding flow F1 (Chunks 1.3)
- ✅ Public profile (Chunk 1.4)
- ✅ find_free_slots алгоритм (Chunk 1.2)
- ✅ SEO базовый (Chunk 1.4): JSON-LD, OG, sitemap, robots, canonical
- ⏳ Booking F2, Manage F3, Reminders F4, Payment F5, GC F6 → Week 2-3
- ⏳ Email-шаблоны → Week 2
- ⏳ Cabinet UI → Week 3
- ⏳ CSV-экспорт income → Week 3
- ⏳ Group session UX → Week 2 (booking) + Week 3 (cabinet)

**Placeholder scan:** нет TBD/TODO.

**Type consistency:** `auto_onboard_tutor` возвращает `(User, LessioTutorProfile | None)`, `create_tutor_profile` — `LessioTutorProfile`, `create_services_from_template` — `list[LessioService]`, `find_free_slots` — `list[datetime]`. Везде согласовано.

**Ambiguity:** `find_free_slots` алгоритм buffer — buffer **до и после** existing booking (через `start_with_buffer` / `end_with_buffer`). Slot-step тоже включает buffer (`duration + buffer`). Это согласовано.
