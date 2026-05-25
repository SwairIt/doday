# Lessio Web MVP — Week 2: Booking flow + Email + Manage-token + Reminders cron

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) или superpowers:subagent-driven-development. Шаги checkbox (`- [ ]`).

**Goal:** End-to-end booking flow: anon-клиент видит `/u/<slug>` → выбирает услугу+слот → форма (email/phone/name) → POST создаёт `LessioBooking` + email клиенту с magic-link + email репетитору. Клиент по `/lessio/manage/<token>` видит свои записи, может отменить/перенести. Cron каждые 5 мин шлёт reminders 24h и 1h.

**Architecture:** All booking persistence в `service.create_booking()` (генерит `manage_token = secrets.token_urlsafe(48)`, INSERT + commit). Email-отправка через расширение существующего `app/auth/email.py` — добавляем 6 lessio-templates. Cron-endpoint `/api/lessio/cron/dispatch-reminders` с X-Cron-Token (тот же что для digest).

**Tech Stack:** Python 3.12 / FastAPI / async SQLAlchemy / Jinja2 / HTMX / Tailwind CDN / aiosmtplib / secrets.

**Spec:** [`docs/superpowers/specs/2026-05-25-lessio-web-mvp-design.md`](../specs/2026-05-25-lessio-web-mvp-design.md) (F2–F5)

**Wk1 baseline (prod SHA 37d06d3):** ✅ models расширены, ✅ migration 0042 применена, ✅ find_free_slots работает, ✅ /lessio/auth/register + setup-profile живые, ✅ /u/<slug> публичен с JSON-LD.

---

## File Structure (week 2)

**Create:**
- `app/lessio/email.py` — 6 send-функций (booking_confirmed/new_booking/reminder_24h/reminder_1h/cancelled_by_client/cancelled_by_tutor)
- `app/lessio/cron.py` — `dispatch_reminders()` cron handler
- `app/templates/lessio/u/book.html` — выбор слота + клиент-форма
- `app/templates/lessio/u/booked.html` — success после booking
- `app/templates/lessio/manage/index.html` — клиент управляет записями по magic-link
- `app/templates/lessio/manage/cancel_confirm.html` — confirm dialog для отмены
- `app/templates/lessio/manage/reschedule.html` — выбор нового слота
- `app/templates/lessio/email/_base.html` — shared email shell (фиолетовый Lessio-стиль)
- `app/templates/lessio/email/booking_confirmed.html|.txt`
- `app/templates/lessio/email/new_booking.html|.txt`
- `app/templates/lessio/email/reminder_24h.html|.txt`
- `app/templates/lessio/email/reminder_1h.html|.txt`
- `app/templates/lessio/email/cancelled_by_client.html|.txt`
- `app/templates/lessio/email/cancelled_by_tutor.html|.txt`
- `tests/test_lessio_web_booking_flow.py` — 6 кейсов (anon-booking, dup-email upsert, group, slot taken, email-fired)
- `tests/test_lessio_web_manage_token.py` — 5 кейсов (page, cancel, reschedule, wrong-token 404, past-bookings hidden)
- `tests/test_lessio_web_reminders.py` — 4 кейса (24h-batch, 1h-batch, idempotency, X-Cron-Token guard)
- `tests/test_lessio_web_email.py` — 3 smoke-кейса render (без отправки)

**Modify:**
- `app/lessio/service.py` — `create_booking()`, `cancel_booking()`, `reschedule_booking()` (новые)
- `app/lessio/web_router.py` — `/u/<slug>/book/<service_id>` (GET+POST), `/lessio/manage/<token>` (GET), `/lessio/manage/<token>/cancel` (POST), `/lessio/manage/<token>/reschedule` (GET+POST), `/api/lessio/cron/dispatch-reminders` (POST)
- `app/templates/lessio/u/profile.html` — service card href меняется с `/u/{slug}/book/{id}` уже на месте — проверить
- `pyproject.toml` — добавить per-file-ignores для новых русско-комментированных файлов

---

## Chunk 2.1: Email-infrastructure + create_booking service

**Files:**
- Create: `app/lessio/email.py`
- Modify: `app/lessio/service.py` — `create_booking`, `cancel_booking`, `reschedule_booking`
- Create: `app/templates/lessio/email/_base.html`
- Create: `app/templates/lessio/email/booking_confirmed.html|.txt`, `new_booking.html|.txt`, `cancelled_by_client.html|.txt`, `cancelled_by_tutor.html|.txt`
- Test: `tests/test_lessio_web_booking_flow.py` (6 кейсов — booking service-уровень + email-mock проверки)
- Test: `tests/test_lessio_web_email.py` (3 кейса — render shell без SMTP)

### Steps

- [ ] **Step 1: Failing-test `tests/test_lessio_web_booking_flow.py`**

```python
"""Booking service: create_booking + cancel + reschedule, email side-effects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking, LessioClient, LessioService
from app.lessio.service import (
    BookingConflictError,
    auto_onboard_tutor,
    cancel_booking,
    create_booking,
    create_services_from_template,
    create_tutor_profile,
)


async def _setup(session: AsyncSession, *, tg_id: int = 40000001):
    user, _ = await auto_onboard_tutor(session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(session, user=user, slug=f"book_{tg_id}", display_name="T")
    services = await create_services_from_template(session, tutor=tutor, niche="english")
    await session.commit()
    return tutor, services[0]


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_create_booking_creates_client_booking_and_sends_emails(
    mock_send, db_session: AsyncSession
) -> None:
    tutor, service = await _setup(db_session)
    slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)

    booking = await create_booking(
        db_session,
        tutor=tutor,
        service=service,
        slot=slot,
        client_email="kid@example.com",
        client_phone="+79991234567",
        client_full_name="Vasya",
    )
    await db_session.commit()

    assert booking.status == "confirmed"
    assert booking.payment_status == "unpaid"
    assert len(booking.manage_token) >= 32
    assert booking.client_email == "kid@example.com"
    assert booking.client_full_name == "Vasya"

    client = (
        await db_session.execute(
            select(LessioClient).where(LessioClient.email == "kid@example.com")
        )
    ).scalar_one()
    assert client.full_name == "Vasya"
    assert client.tutor_id == tutor.id

    mock_send.assert_awaited_once()
    kwargs = mock_send.await_args.kwargs
    assert kwargs["booking"].id == booking.id


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_repeat_booking_same_email_updates_client_full_name(
    mock_send, db_session: AsyncSession
) -> None:
    tutor, service = await _setup(db_session, tg_id=40000002)
    slot1 = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
    slot2 = datetime(2026, 6, 9, 14, 0, tzinfo=UTC)

    await create_booking(
        db_session, tutor=tutor, service=service, slot=slot1,
        client_email="re@e.com", client_full_name="Old Name", client_phone=None,
    )
    await create_booking(
        db_session, tutor=tutor, service=service, slot=slot2,
        client_email="re@e.com", client_full_name="New Name", client_phone="+79990000000",
    )
    await db_session.commit()

    clients = (
        await db_session.execute(select(LessioClient).where(LessioClient.email == "re@e.com"))
    ).scalars().all()
    assert len(clients) == 1
    assert clients[0].full_name == "New Name"
    assert clients[0].phone == "+79990000000"


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_booking_conflict_raises_for_individual_service(
    mock_send, db_session: AsyncSession
) -> None:
    import pytest

    tutor, service = await _setup(db_session, tg_id=40000003)
    slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)

    await create_booking(
        db_session, tutor=tutor, service=service, slot=slot,
        client_email="a@e.com", client_full_name="A", client_phone=None,
    )
    await db_session.commit()

    with pytest.raises(BookingConflictError):
        await create_booking(
            db_session, tutor=tutor, service=service, slot=slot,
            client_email="b@e.com", client_full_name="B", client_phone=None,
        )


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_group_session_allows_multiple_bookings(
    mock_send, db_session: AsyncSession
) -> None:
    tutor, _ = await _setup(db_session, tg_id=40000004)
    group = LessioService(
        tutor_id=tutor.id, title="Yoga", duration_minutes=60,
        price_kopecks=80000, price_stars=80,
        is_group_session=True, max_attendees=3,
    )
    db_session.add(group)
    await db_session.commit()

    slot = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)
    for i in range(3):
        await create_booking(
            db_session, tutor=tutor, service=group, slot=slot,
            client_email=f"g{i}@e.com", client_full_name=f"G{i}", client_phone=None,
        )
        await db_session.commit()

    bookings = (
        await db_session.execute(
            select(LessioBooking).where(LessioBooking.service_id == group.id)
        )
    ).scalars().all()
    assert len(bookings) == 3


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_group_session_full_raises(mock_send, db_session: AsyncSession) -> None:
    import pytest

    tutor, _ = await _setup(db_session, tg_id=40000005)
    group = LessioService(
        tutor_id=tutor.id, title="Yoga", duration_minutes=60,
        price_kopecks=80000, price_stars=80,
        is_group_session=True, max_attendees=2,
    )
    db_session.add(group)
    await db_session.commit()

    slot = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)
    for i in range(2):
        await create_booking(
            db_session, tutor=tutor, service=group, slot=slot,
            client_email=f"g{i}@e.com", client_full_name=f"G{i}", client_phone=None,
        )
        await db_session.commit()

    with pytest.raises(BookingConflictError):
        await create_booking(
            db_session, tutor=tutor, service=group, slot=slot,
            client_email="overflow@e.com", client_full_name="Overflow", client_phone=None,
        )


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
async def test_cancel_booking_marks_status_and_sends_email(
    mock_send, db_session: AsyncSession
) -> None:
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        tutor, service = await _setup(db_session, tg_id=40000006)
        slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
        booking = await create_booking(
            db_session, tutor=tutor, service=service, slot=slot,
            client_email="c@e.com", client_full_name="C", client_phone=None,
        )
        await db_session.commit()

    await cancel_booking(db_session, booking=booking, by="client")
    await db_session.commit()

    assert booking.status == "cancelled"
    assert booking.cancelled_at is not None
    mock_send.assert_awaited_once()
```

Expected: FAIL — `create_booking` / `cancel_booking` / `BookingConflictError` / `send_booking_emails` ещё не существуют.

- [ ] **Step 2: Run failing test**
```bash
uv run pytest tests/test_lessio_web_booking_flow.py -v
```
Expected: ImportError / NameError.

- [ ] **Step 3: Implement `app/lessio/email.py`**

```python
"""Lessio email-уведомления — booking, cancel, reminders.

Все функции async, ловят SMTPError и логируют (не raise) — отправка email
никогда не должна блокировать booking-транзакцию или cron-batch.
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
    """Returns True on success, False on SMTP error (logged)."""
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
    except Exception as exc:  # noqa: BLE001 — SMTP может бросать что угодно
        _log.warning("lessio_email_send_failed", to=to, subject=subject, error=str(exc))
        return False


def _ctx(booking: LessioBooking, tutor: LessioTutorProfile, **extra: Any) -> dict[str, Any]:
    return {
        "tutor": tutor,
        "booking": booking,
        "manage_url": f"{_base_url()}/lessio/manage/{booking.manage_token}",
        "profile_url": f"{_base_url()}/u/{tutor.slug}",
        "meeting_url": booking.meeting_url or tutor.default_meeting_url_template or "",
        **extra,
    }


async def send_booking_emails(
    *, booking: LessioBooking, tutor: LessioTutorProfile, service_title: str
) -> None:
    """Двойная рассылка после нового booking: клиенту (с magic-link) + репетитору."""
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
    *, booking: LessioBooking, tutor: LessioTutorProfile, by: str, service_title: str
) -> None:
    """by ∈ {client, tutor} — определяет получателя."""
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
    *, booking: LessioBooking, tutor: LessioTutorProfile, service_title: str, hours: int
) -> bool:
    """24h или 1h reminder клиенту. Returns True если SMTP ОК (для UPDATE timestamp)."""
    ctx = _ctx(booking, tutor, service_title=service_title, hours=hours)
    tmpl = "reminder_24h" if hours == 24 else "reminder_1h"
    html = _env.get_template(f"{tmpl}.html").render(**ctx)
    text = _env.get_template(f"{tmpl}.txt").render(**ctx)
    subject_prefix = "Завтра в" if hours == 24 else "Через час:"
    subject = f"{subject_prefix} {service_title} · {tutor.display_name}"
    return await _send(to=booking.client_email, subject=subject, html=html, text=text)
```

- [ ] **Step 4: Email шаблоны (_base.html + 4 booking-уведомления)**

Create `app/templates/lessio/email/_base.html` — shared shell (фиолетовый градиент header + white card + footer):
```html
{# Минималистичный single-card layout. Inline-CSS обязательно — Gmail strip'ит <style>. #}
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>{% block title %}Lessio{% endblock %}</title></head>
<body style="margin:0;padding:0;background:#0d0820;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#1a1230;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:linear-gradient(180deg,#0f0a1f 0%,#2e1065 100%);">
<tr><td align="center" style="padding:40px 16px;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
         style="max-width:560px;background:#ffffff;border-radius:24px;
                box-shadow:0 20px 60px -10px rgba(124,58,237,.5);overflow:hidden;">
    <tr><td style="background:linear-gradient(135deg,#7c3aed,#d946ef);height:6px;font-size:0;">&nbsp;</td></tr>
    <tr><td style="padding:36px 40px 28px 40px;">
      <div style="text-align:center;margin-bottom:24px;">
        <span style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#d946ef);
                     color:#fff;font-weight:800;font-size:18px;padding:8px 14px;border-radius:10px;">
          ✦ Lessio
        </span>
      </div>
      {% block content %}{% endblock %}
    </td></tr>
    <tr><td style="background:#faf5ff;padding:18px 40px;text-align:center;
                   color:#7c3aed;font-size:12px;border-top:1px solid #ede9fe;">
      Powered by <a href="https://getdoday.ru/lessio" style="color:#7c3aed;">Lessio</a>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
```

Create `booking_confirmed.html` (клиенту):
```html
{% extends "_base.html" %}
{% block title %}Вы записаны{% endblock %}
{% block content %}
<h1 style="margin:0 0 16px 0;font-size:24px;color:#1a1230;">✅ Вы записаны</h1>
<p style="font-size:16px;line-height:1.55;color:#444;margin:0 0 16px 0;">
  Здравствуйте, {{ booking.client_full_name }}!
</p>
<p style="font-size:16px;line-height:1.55;color:#444;margin:0 0 24px 0;">
  Ваша запись к <b>{{ tutor.display_name }}</b> подтверждена:
</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:#faf5ff;border-radius:12px;padding:0;margin-bottom:24px;">
<tr><td style="padding:18px 20px;">
  <div style="font-size:15px;color:#7c3aed;margin-bottom:6px;">{{ service_title }}</div>
  <div style="font-size:22px;font-weight:800;color:#1a1230;">
    {{ booking.starts_at.strftime('%d.%m.%Y') }} в {{ booking.starts_at.strftime('%H:%M') }} UTC
  </div>
  <div style="font-size:14px;color:#666;margin-top:6px;">
    Длительность: {{ booking.duration_minutes }} мин
  </div>
</td></tr>
</table>
{% if meeting_url %}
<p style="font-size:15px;margin:0 0 20px 0;">
  <b>Ссылка на встречу:</b><br>
  <a href="{{ meeting_url }}" style="color:#7c3aed;word-break:break-all;">{{ meeting_url }}</a>
</p>
{% endif %}
<p style="text-align:center;margin:28px 0;">
  <a href="{{ manage_url }}"
     style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#d946ef);
            color:#fff;text-decoration:none;font-weight:700;padding:14px 28px;border-radius:12px;">
    Управление записью →
  </a>
</p>
<p style="font-size:13px;color:#888;margin:0;text-align:center;">
  По этой ссылке вы сможете перенести или отменить запись.
</p>
{% endblock %}
```

Create `booking_confirmed.txt`:
```
Здравствуйте, {{ booking.client_full_name }}!

Ваша запись к {{ tutor.display_name }} подтверждена:

{{ service_title }}
{{ booking.starts_at.strftime('%d.%m.%Y в %H:%M') }} UTC
Длительность: {{ booking.duration_minutes }} мин

{% if meeting_url %}Ссылка на встречу: {{ meeting_url }}{% endif %}

Управление записью (отмена / перенос): {{ manage_url }}

—
Lessio · {{ profile_url }}
```

Create `new_booking.html` (репетитору) — копия с другим текстом:
```html
{% extends "_base.html" %}
{% block content %}
<h1 style="margin:0 0 16px 0;font-size:24px;">🎯 Новая запись</h1>
<p style="font-size:16px;color:#444;margin:0 0 20px 0;">
  {{ booking.client_full_name }} ({{ booking.client_email }}) записался(-ась):
</p>
<table role="presentation" width="100%" style="background:#faf5ff;border-radius:12px;margin-bottom:20px;">
<tr><td style="padding:18px 20px;">
  <div style="font-size:15px;color:#7c3aed;">{{ service_title }}</div>
  <div style="font-size:22px;font-weight:800;">
    {{ booking.starts_at.strftime('%d.%m.%Y · %H:%M') }} UTC
  </div>
</td></tr>
</table>
<p style="font-size:14px;color:#666;">
  Открыть кабинет: <a href="{{ profile_url | replace('/u/', '/lessio/app/today') }}"
                       style="color:#7c3aed;">Lessio Today</a>
</p>
{% endblock %}
```

Create `new_booking.txt`:
```
Новая запись от {{ booking.client_full_name }} ({{ booking.client_email }}):

{{ service_title }}
{{ booking.starts_at.strftime('%d.%m.%Y · %H:%M') }} UTC

Кабинет: https://getdoday.ru/lessio/app/today
```

Create `cancelled_by_client.html` (репетитору) и `cancelled_by_tutor.html` (клиенту) — short notification аналогично, с заголовком ❌ Отменено и фактами встречи.

```html
{# cancelled_by_client.html — репетитору #}
{% extends "_base.html" %}
{% block content %}
<h1 style="margin:0 0 16px 0;font-size:22px;">❌ Запись отменена клиентом</h1>
<p style="font-size:16px;color:#444;">
  {{ booking.client_full_name }} отменил(-а) запись на
  <b>{{ booking.starts_at.strftime('%d.%m.%Y · %H:%M') }} UTC</b> ({{ service_title }}).
</p>
{% endblock %}
```
```
{# cancelled_by_client.txt #}
{{ booking.client_full_name }} отменил(-а) запись:
{{ service_title }} — {{ booking.starts_at.strftime('%d.%m.%Y %H:%M') }} UTC
```

```html
{# cancelled_by_tutor.html — клиенту #}
{% extends "_base.html" %}
{% block content %}
<h1 style="margin:0 0 16px 0;font-size:22px;">❌ Запись отменена</h1>
<p style="font-size:16px;color:#444;">
  Здравствуйте, {{ booking.client_full_name }}. К сожалению, репетитор
  {{ tutor.display_name }} отменил вашу запись на
  <b>{{ booking.starts_at.strftime('%d.%m.%Y · %H:%M') }} UTC</b> ({{ service_title }}).
</p>
<p style="font-size:15px;margin-top:18px;">
  Можно записаться на другое время:
  <a href="{{ profile_url }}" style="color:#7c3aed;">{{ profile_url }}</a>
</p>
{% endblock %}
```
```
{# cancelled_by_tutor.txt #}
Здравствуйте, {{ booking.client_full_name }}.

Репетитор {{ tutor.display_name }} отменил запись:
{{ service_title }} — {{ booking.starts_at.strftime('%d.%m.%Y %H:%M') }} UTC

Другие свободные слоты: {{ profile_url }}
```

- [ ] **Step 5: Implement `create_booking` / `cancel_booking` в service.py**

Append (после `create_services_from_template`):

```python
import secrets

from app.lessio.email import send_booking_emails, send_cancellation_email


class BookingConflictError(Exception):
    """Slot занят / group session full."""


async def create_booking(
    session: AsyncSession,
    *,
    tutor: LessioTutorProfile,
    service: LessioService,
    slot: datetime,
    client_email: str,
    client_full_name: str,
    client_phone: str | None,
    notes: str | None = None,
) -> LessioBooking:
    """Anon-клиент создаёт booking. Atomic transaction:
    find/create LessioClient → INSERT LessioBooking (status=confirmed) →
    enqueue email (вне транзакции — после commit'а вызывающим кодом).

    Raises BookingConflictError если slot занят (для индивидуальной) или
    group session full.
    """
    # 1) Conflict check (app-level, см. migration 0042)
    existing_q = await session.execute(
        select(LessioBooking).where(
            LessioBooking.tutor_id == tutor.id,
            LessioBooking.starts_at == slot,
            LessioBooking.status.in_(["confirmed", "completed"]),
        )
    )
    existing = existing_q.scalars().all()
    if service.is_group_session:
        same_service = [b for b in existing if b.service_id == service.id]
        if len(same_service) >= service.max_attendees:
            raise BookingConflictError("Группа уже заполнена")
        # Если другая (индивидуальная) услуга уже забронирована на этот же starts_at — конфликт
        if any(b.service_id != service.id for b in existing):
            raise BookingConflictError("Это время уже занято другой встречей")
    else:
        if existing:
            raise BookingConflictError("Это время уже занято")

    # 2) find/upsert LessioClient by (tutor_id, email)
    email_norm = client_email.lower().strip()
    client = (
        await session.execute(
            select(LessioClient).where(
                LessioClient.tutor_id == tutor.id, LessioClient.email == email_norm
            )
        )
    ).scalar_one_or_none()
    if client is None:
        client = LessioClient(
            tutor_id=tutor.id,
            email=email_norm,
            phone=client_phone,
            full_name=client_full_name[:120],
            telegram_user_id=None,
        )
        session.add(client)
        await session.flush()
    else:
        client.full_name = client_full_name[:120]
        if client_phone:
            client.phone = client_phone

    # 3) INSERT booking
    booking = LessioBooking(
        tutor_id=tutor.id,
        client_id=client.id,
        service_id=service.id,
        starts_at=slot,
        duration_minutes=service.duration_minutes,
        status="confirmed",
        price_kopecks=service.price_kopecks,
        price_stars=service.price_stars,
        notes=notes,
        manage_token=secrets.token_urlsafe(48),
        meeting_url=service.meeting_url_template or tutor.default_meeting_url_template,
        payment_status="unpaid",
        client_email=email_norm,
        client_full_name=client_full_name[:120],
    )
    session.add(booking)
    await session.flush()

    # 4) Email (after-commit вызывает router; service делает direct call ради простоты тестов
    #    через mock-patch)
    await send_booking_emails(
        booking=booking, tutor=tutor, service_title=service.title
    )
    return booking


async def cancel_booking(
    session: AsyncSession,
    *,
    booking: LessioBooking,
    by: str,  # "client" or "tutor"
) -> LessioBooking:
    """Mark cancelled + send email опровергающее сторону."""
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    await session.flush()

    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    service = await session.get(LessioService, booking.service_id)
    if tutor and service:
        await send_cancellation_email(
            booking=booking, tutor=tutor, by=by, service_title=service.title
        )
    return booking


async def reschedule_booking(
    session: AsyncSession,
    *,
    booking: LessioBooking,
    new_slot: datetime,
    by: str,  # "client" or "tutor"
) -> LessioBooking:
    """Перенос — cancel + create новый с теми же client/service/денеж-полями. Возвращает новый."""
    old_status = booking.status
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    await session.flush()

    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    service = await session.get(LessioService, booking.service_id)
    if tutor is None or service is None:
        booking.status = old_status
        raise BookingConflictError("Tutor or service missing — cannot reschedule")

    new = await create_booking(
        session,
        tutor=tutor,
        service=service,
        slot=new_slot,
        client_email=booking.client_email,
        client_full_name=booking.client_full_name,
        client_phone=None,  # клиент уже existing, phone подхватится upsert'ом
        notes=booking.notes,
    )
    return new
```

Add to `__all__`: `BookingConflictError`, `create_booking`, `cancel_booking`, `reschedule_booking`.

- [ ] **Step 6: Add pyproject ignores**

```toml
"app/lessio/email.py" = ["RUF001", "RUF002", "RUF003"]
```

- [ ] **Step 7: Run all booking tests**

```bash
uv run pytest tests/test_lessio_web_booking_flow.py -v
```
Expected: 6 passed.

- [ ] **Step 8: Email-render smoke test**

Create `tests/test_lessio_web_email.py`:
```python
"""Email-templates render-only smoke (без SMTP — проверяем что Jinja собирает HTML)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.lessio.email import (
    send_booking_emails,
    send_cancellation_email,
    send_reminder_email,
)


def _booking_stub():
    class B:
        client_full_name = "Тест Клиент"
        client_email = "stub@example.com"
        starts_at = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
        duration_minutes = 60
        manage_token = "x" * 48
        meeting_url = "https://meet.example/abc"
    return B()


def _tutor_stub():
    class T:
        display_name = "Tutor Test"
        slug = "tutor_test"
        notification_email = "tutor@example.com"
        default_meeting_url_template = None
    return T()


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_booking_emails_renders_both(mock_send) -> None:
    await send_booking_emails(
        booking=_booking_stub(), tutor=_tutor_stub(), service_title="Английский 60 мин"
    )
    assert mock_send.await_count == 2  # client + tutor


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_cancellation_to_client(mock_send) -> None:
    await send_cancellation_email(
        booking=_booking_stub(), tutor=_tutor_stub(), by="tutor", service_title="Y"
    )
    args = mock_send.await_args
    msg = args.args[0]
    assert msg["To"] == "stub@example.com"


@patch("app.lessio.email.aiosmtplib.send", new_callable=AsyncMock)
async def test_send_reminder_returns_true_on_success(mock_send) -> None:
    ok = await send_reminder_email(
        booking=_booking_stub(), tutor=_tutor_stub(), service_title="Y", hours=24
    )
    assert ok is True
    assert mock_send.await_count == 1
```

- [ ] **Step 9: Run all booking+email tests + full lint**
```bash
uv run pytest tests/test_lessio_web_booking_flow.py tests/test_lessio_web_email.py -v
uv run ruff check && uv run mypy --strict app/ scripts/
```

- [ ] **Step 10: Commit + push**
```bash
git add -A
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m \
  "Lessio Web MVP chunk 2.1 — create_booking service + email infra + 4 booking-email templates"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Chunk 2.2: Public booking flow `/u/<slug>/book/<service_id>`

**Files:**
- Modify: `app/lessio/web_router.py` — добавить GET+POST `/u/<slug>/book/<service_id>`, GET `/u/<slug>/booked` (success)
- Create: `app/templates/lessio/u/book.html` — слот-picker + клиент-форма
- Create: `app/templates/lessio/u/booked.html` — success
- Test: integration кейсы в `tests/test_lessio_web_booking_flow.py` (добавить ~4 router-level)

### Steps

- [ ] **Step 1: Failing-test (extend booking_flow.py)**

```python
async def test_book_page_renders_slots(client, db_session) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=40000010)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="book_pg_t", display_name="T"
    )
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    resp = await client.get(f"/u/book_pg_t/book/{services[0].id}")
    assert resp.status_code == 200
    body = resp.text
    assert "name=\"client_email\"" in body
    assert services[0].title in body
    # Должен быть хотя бы один доступный слот (next 14 days, working_days)
    assert "data-slot=" in body or "Свободных слотов" in body


@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_post_book_creates_booking_and_redirects(
    mock_send, client, db_session
) -> None:
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=40000011)
    tutor = await create_tutor_profile(
        db_session, user=user, slug="book_post_t", display_name="T"
    )
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()

    # Найдём свободный слот через find_free_slots напрямую
    from datetime import UTC, datetime, timedelta
    from app.lessio.service import find_free_slots
    slots = await find_free_slots(
        db_session, tutor,
        date_from=datetime.now(UTC),
        date_to=datetime.now(UTC) + timedelta(days=14),
        service=services[0],
    )
    assert slots

    resp = await client.post(
        f"/u/book_post_t/book/{services[0].id}",
        data={
            "slot_iso": slots[0].isoformat(),
            "client_email": "book@e.com",
            "client_full_name": "Booker",
            "client_phone": "+79991234567",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    assert "/u/book_post_t/booked" in resp.headers["location"]
    mock_send.assert_awaited_once()


async def test_post_book_rejects_taken_slot(client, db_session) -> None:
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        user, _ = await auto_onboard_tutor(db_session, telegram_user_id=40000012)
        tutor = await create_tutor_profile(
            db_session, user=user, slug="book_taken_t", display_name="T"
        )
        services = await create_services_from_template(db_session, tutor=tutor, niche="english")
        await db_session.commit()

        slot = datetime(2026, 6, 8, 14, 0, tzinfo=UTC)
        await create_booking(
            db_session, tutor=tutor, service=services[0], slot=slot,
            client_email="a@e.com", client_full_name="A", client_phone=None,
        )
        await db_session.commit()

    resp = await client.post(
        f"/u/book_taken_t/book/{services[0].id}",
        data={
            "slot_iso": slot.isoformat(),
            "client_email": "b@e.com",
            "client_full_name": "B",
        },
    )
    assert resp.status_code == 400
    assert "занят" in resp.text


async def test_book_page_404_unknown_slug(client) -> None:
    from uuid import uuid4
    resp = await client.get(f"/u/nopedont/book/{uuid4()}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement endpoints в web_router.py (extend `_public_router`)**

```python
@_public_router.get("/u/{slug}/book/{service_id}", response_class=HTMLResponse,
                    include_in_schema=False)
async def book_page(
    slug: str, service_id: UUID, request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = (await session.execute(
        select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
    )).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")
    service = (await session.execute(
        select(LessioService).where(
            LessioService.id == service_id, LessioService.tutor_id == profile.id,
            LessioService.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")

    from app.lessio.service import find_free_slots
    slots = await find_free_slots(
        session, profile,
        date_from=datetime.now(UTC),
        date_to=datetime.now(UTC) + timedelta(days=14),
        service=service,
    )
    return _templates.TemplateResponse(
        request, "lessio/u/book.html",
        {"tutor": profile, "service": service, "slots": slots,
         "canonical_url": f"https://getdoday.ru/u/{profile.slug}/book/{service.id}"},
    )


@_public_router.post("/u/{slug}/book/{service_id}", response_class=HTMLResponse,
                     include_in_schema=False)
async def book_submit(
    slug: str, service_id: UUID, request: Request,
    slot_iso: Annotated[str, Form()],
    client_email: Annotated[str, Form()],
    client_full_name: Annotated[str, Form()],
    client_phone: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.service import BookingConflictError, create_booking

    profile = (await session.execute(
        select(LessioTutorProfile).where(LessioTutorProfile.slug == slug.lower())
    )).scalar_one_or_none()
    if profile is None or not profile.is_active:
        raise HTTPException(404, "Репетитор не найден")
    service = (await session.execute(
        select(LessioService).where(
            LessioService.id == service_id, LessioService.tutor_id == profile.id,
        )
    )).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")

    try:
        slot = datetime.fromisoformat(slot_iso)
    except ValueError:
        return _templates.TemplateResponse(
            request, "lessio/u/book.html",
            {"tutor": profile, "service": service, "slots": [],
             "error": "Некорректный формат времени"},
            status_code=400,
        )

    try:
        booking = await create_booking(
            session, tutor=profile, service=service, slot=slot,
            client_email=client_email, client_full_name=client_full_name,
            client_phone=client_phone, notes=notes,
        )
    except BookingConflictError as exc:
        return _templates.TemplateResponse(
            request, "lessio/u/book.html",
            {"tutor": profile, "service": service, "slots": [],
             "error": str(exc)},
            status_code=400,
        )
    await session.commit()
    return RedirectResponse(f"/u/{profile.slug}/booked?token={booking.manage_token}",
                            status_code=303)


@_public_router.get("/u/{slug}/booked", response_class=HTMLResponse, include_in_schema=False)
async def booked_page(
    slug: str, token: str, request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking = (await session.execute(
        select(LessioBooking).where(LessioBooking.manage_token == token)
    )).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    if tutor is None or tutor.slug != slug.lower():
        raise HTTPException(404, "Запись не найдена")
    return _templates.TemplateResponse(
        request, "lessio/u/booked.html",
        {"tutor": tutor, "booking": booking,
         "manage_url": f"/lessio/manage/{booking.manage_token}"},
    )
```

Импорты для router.py: `from datetime import UTC, datetime, timedelta`, `from uuid import UUID`, `from app.lessio.models import LessioBooking, LessioService` (LessioBooking уже импортирован).

- [ ] **Step 4: Создать `app/templates/lessio/u/book.html`**

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Запись · {{ service.title }} · {{ tutor.display_name }}</title>
  <meta name="robots" content="noindex,follow">  {# booking-форма — без index #}
  <link rel="canonical" href="{{ canonical_url }}">
  <link rel="icon" href="/favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body{background:linear-gradient(180deg,#0f0a1f,#2e1065);color:#f5f3ff;
              font-family:-apple-system,Segoe UI,sans-serif;min-height:100vh;}</style>
</head>
<body class="antialiased">
<main class="mx-auto max-w-2xl px-5 py-12">
  <a href="/u/{{ tutor.slug }}" class="text-violet-300/70 text-sm hover:text-violet-200">
    ← {{ tutor.display_name }}
  </a>

  <h1 class="text-3xl font-extrabold mt-4 mb-2">{{ service.title }}</h1>
  <p class="text-violet-200/70 mb-8">
    {{ service.duration_minutes }} мин ·
    <span class="font-bold text-white">{{ "{:,}".format(service.price_kopecks // 100).replace(',', ' ') }} ₽</span>
    {% if service.is_group_session %}· группа до {{ service.max_attendees }}{% endif %}
  </p>

  {% if error %}
  <div class="mb-6 px-4 py-3 rounded-xl bg-rose-500/15 text-rose-300">{{ error }}</div>
  {% endif %}

  <form method="post" action="/u/{{ tutor.slug }}/book/{{ service.id }}"
        class="space-y-5 bg-white/5 border border-white/10 rounded-2xl p-5"
        x-data="{ slot: null }">

    <div>
      <span class="text-sm font-semibold mb-2 block">Выбери время</span>
      {% if slots %}
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-64 overflow-y-auto p-1">
        {% for s in slots %}
        <button type="button" data-slot="{{ s.isoformat() }}"
                x-on:click="slot='{{ s.isoformat() }}'"
                x-bind:class="slot==='{{ s.isoformat() }}' ? 'bg-violet-500 border-violet-400' : 'bg-white/5 border-white/10'"
                class="px-3 py-2 border rounded-lg text-sm hover:border-violet-400 transition">
          {{ s.strftime('%d.%m %H:%M') }}
        </button>
        {% endfor %}
      </div>
      <input type="hidden" name="slot_iso" x-bind:value="slot" required>
      {% else %}
      <p class="text-violet-300/50 text-sm">Свободных слотов на ближайшие 2 недели нет.</p>
      {% endif %}
    </div>

    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Ваше имя</span>
      <input name="client_full_name" type="text" required maxlength="120"
             class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-violet-400">
    </label>

    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Email</span>
      <input name="client_email" type="email" required maxlength="255"
             class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-violet-400">
      <span class="text-xs text-violet-300/40 mt-1 block">Туда придёт ссылка на встречу + управление записью</span>
    </label>

    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Телефон (опционально)</span>
      <input name="client_phone" type="tel" maxlength="50"
             class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-violet-400">
    </label>

    <label class="block">
      <span class="text-sm font-semibold mb-1.5 block">Комментарий (опционально)</span>
      <textarea name="notes" rows="2" maxlength="500"
                class="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg resize-none"></textarea>
    </label>

    <button {% if not slots %}disabled{% endif %}
            class="w-full px-6 py-3.5 bg-gradient-to-r from-violet-500 to-pink-500 rounded-xl font-bold hover:opacity-90 transition disabled:opacity-30">
      Записаться →
    </button>
  </form>

  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</main>
</body>
</html>
```

- [ ] **Step 5: Create `app/templates/lessio/u/booked.html`**

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"><title>Запись подтверждена · {{ tutor.display_name }}</title>
  <meta name="robots" content="noindex,nofollow">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body{background:linear-gradient(180deg,#0f0a1f,#2e1065);color:#f5f3ff;
              font-family:-apple-system,Segoe UI,sans-serif;min-height:100vh;}</style>
</head>
<body>
<main class="mx-auto max-w-md py-12 px-5 text-center">
  <div class="text-6xl mb-4">✅</div>
  <h1 class="text-3xl font-extrabold mb-3">Записано!</h1>
  <p class="text-violet-200/70 mb-6">
    Подтверждение и ссылка на встречу отправлены на <b>{{ booking.client_email }}</b>.
  </p>
  <div class="bg-white/5 border border-white/10 rounded-2xl p-5 mb-6 text-left">
    <div class="text-sm text-violet-300/70 mb-2">{{ booking.starts_at.strftime('%d.%m.%Y') }}</div>
    <div class="text-2xl font-bold mb-2">{{ booking.starts_at.strftime('%H:%M') }} UTC</div>
    <div class="text-sm text-violet-300/70">{{ booking.duration_minutes }} мин · {{ tutor.display_name }}</div>
  </div>
  <a href="{{ manage_url }}"
     class="inline-block px-6 py-3 bg-white/10 rounded-xl font-semibold hover:bg-white/20 transition">
    Управление записью
  </a>
  <p class="text-xs text-violet-300/40 mt-8">
    Закладывай ссылку — по ней можно перенести или отменить запись.
  </p>
</main>
</body>
</html>
```

- [ ] **Step 6: Run tests + lint, commit + push**

```bash
uv run pytest tests/test_lessio_web_booking_flow.py -v
uv run ruff check && uv run mypy --strict app/ scripts/
git add -A
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m \
  "Lessio Web MVP chunk 2.2 — public booking flow /u/<slug>/book/<service_id>"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

---

## Chunk 2.3: Magic-link manage flow `/lessio/manage/<token>`

**Files:**
- Modify: `app/lessio/web_router.py` — добавить /lessio/manage/<token> GET (страница) + POST cancel + GET/POST reschedule
- Create: `app/templates/lessio/manage/index.html`
- Create: `app/templates/lessio/manage/cancel_confirm.html`
- Create: `app/templates/lessio/manage/reschedule.html`
- Test: `tests/test_lessio_web_manage_token.py` (5 кейсов)

### Steps

- [ ] **Step 1: Failing-test `tests/test_lessio_web_manage_token.py`**

```python
"""Magic-link manage: /lessio/manage/<token> — view + cancel + reschedule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioBooking
from app.lessio.service import (
    auto_onboard_tutor, create_booking, create_services_from_template, create_tutor_profile,
)


async def _booked(db_session, *, tg_id=50000001, slot=None):
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"mng_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    slot = slot or (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session, tutor=tutor, service=services[0], slot=slot,
            client_email="m@e.com", client_full_name="M", client_phone=None,
        )
        await db_session.commit()
    return tutor, services[0], booking


async def test_manage_page_renders_booking(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, booking = await _booked(db_session)
    resp = await client.get(f"/lessio/manage/{booking.manage_token}")
    assert resp.status_code == 200
    assert booking.client_email in resp.text or "M" in resp.text


async def test_manage_404_for_unknown_token(client: AsyncClient) -> None:
    resp = await client.get("/lessio/manage/" + "z" * 64)
    assert resp.status_code == 404


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
async def test_manage_cancel(mock_send, client, db_session) -> None:
    _, _, booking = await _booked(db_session, tg_id=50000002)
    resp = await client.post(f"/lessio/manage/{booking.manage_token}/cancel",
                             follow_redirects=False)
    assert resp.status_code in (302, 303)
    refreshed = (await db_session.execute(
        select(LessioBooking).where(LessioBooking.id == booking.id)
    )).scalar_one()
    assert refreshed.status == "cancelled"
    mock_send.assert_awaited_once()


@patch("app.lessio.service.send_cancellation_email", new_callable=AsyncMock)
@patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock)
async def test_manage_reschedule(mock_book, mock_cancel, client, db_session) -> None:
    tutor, service, booking = await _booked(db_session, tg_id=50000003)
    from app.lessio.service import find_free_slots
    new_slots = await find_free_slots(
        db_session, tutor,
        date_from=datetime.now(UTC) + timedelta(days=3),
        date_to=datetime.now(UTC) + timedelta(days=10),
        service=service,
    )
    new_slot = new_slots[0]
    resp = await client.post(f"/lessio/manage/{booking.manage_token}/reschedule",
                             data={"slot_iso": new_slot.isoformat()},
                             follow_redirects=False)
    assert resp.status_code in (302, 303)
    # Старый — cancelled
    old = (await db_session.execute(
        select(LessioBooking).where(LessioBooking.id == booking.id)
    )).scalar_one()
    assert old.status == "cancelled"
    # Новый exists с другим starts_at
    actives = (await db_session.execute(
        select(LessioBooking).where(LessioBooking.status == "confirmed")
    )).scalars().all()
    assert len(actives) == 1
    assert actives[0].starts_at == new_slot
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement manage endpoints в web_router.py**

```python
@router.get("/manage/{token}", response_class=HTMLResponse, include_in_schema=False)
async def manage_page(
    token: str, request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    booking = (await session.execute(
        select(LessioBooking).where(LessioBooking.manage_token == token)
    )).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    service = await session.get(LessioService, booking.service_id)
    if tutor is None or service is None:
        raise HTTPException(404, "Запись не найдена")
    # Все будущие записи клиента у ЭТОГО репетитора (по client_email)
    siblings = (await session.execute(
        select(LessioBooking).where(
            LessioBooking.tutor_id == tutor.id,
            LessioBooking.client_email == booking.client_email,
            LessioBooking.starts_at >= datetime.now(UTC),
            LessioBooking.status == "confirmed",
        ).order_by(LessioBooking.starts_at)
    )).scalars().all()
    return _templates.TemplateResponse(
        request, "lessio/manage/index.html",
        {"booking": booking, "tutor": tutor, "service": service, "siblings": siblings},
    )


@router.post("/manage/{token}/cancel", response_class=HTMLResponse, include_in_schema=False)
async def manage_cancel(
    token: str, session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.service import cancel_booking
    booking = (await session.execute(
        select(LessioBooking).where(LessioBooking.manage_token == token)
    )).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    await cancel_booking(session, booking=booking, by="client")
    await session.commit()
    return RedirectResponse(f"/lessio/manage/{token}", status_code=303)


@router.get("/manage/{token}/reschedule", response_class=HTMLResponse, include_in_schema=False)
async def manage_reschedule_page(
    token: str, request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.service import find_free_slots
    booking = (await session.execute(
        select(LessioBooking).where(LessioBooking.manage_token == token)
    )).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    tutor = await session.get(LessioTutorProfile, booking.tutor_id)
    service = await session.get(LessioService, booking.service_id)
    if tutor is None or service is None:
        raise HTTPException(404, "Запись не найдена")
    slots = await find_free_slots(
        session, tutor,
        date_from=datetime.now(UTC), date_to=datetime.now(UTC) + timedelta(days=14),
        service=service,
    )
    return _templates.TemplateResponse(
        request, "lessio/manage/reschedule.html",
        {"booking": booking, "tutor": tutor, "service": service, "slots": slots},
    )


@router.post("/manage/{token}/reschedule", response_class=HTMLResponse, include_in_schema=False)
async def manage_reschedule_submit(
    token: str, slot_iso: Annotated[str, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.service import BookingConflictError, reschedule_booking
    booking = (await session.execute(
        select(LessioBooking).where(LessioBooking.manage_token == token)
    )).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    try:
        new_slot = datetime.fromisoformat(slot_iso)
    except ValueError:
        raise HTTPException(400, "Некорректное время")
    try:
        new = await reschedule_booking(
            session, booking=booking, new_slot=new_slot, by="client"
        )
    except BookingConflictError as exc:
        raise HTTPException(400, str(exc))
    await session.commit()
    return RedirectResponse(f"/lessio/manage/{new.manage_token}", status_code=303)
```

- [ ] **Step 4: Templates: index.html, reschedule.html (skip cancel_confirm — straight POST)**

`manage/index.html` — список записей + кнопки [Перенести] [Отменить] для каждой confirmed-будущей. Если booking.status='cancelled' — banner «Запись отменена».

`manage/reschedule.html` — копия `book.html` с заголовком «Перенос». POST на `/manage/<token>/reschedule`.

(Полный HTML опускаем для краткости — копировать структуру из `book.html`/`booked.html`, менять hidden token + action URL.)

- [ ] **Step 5: Lint+tests+commit+push**

---

## Chunk 2.4: Cron reminders `/api/lessio/cron/dispatch-reminders`

**Files:**
- Create: `app/lessio/cron.py` — `dispatch_reminders()` handler
- Create: `app/templates/lessio/email/reminder_24h.html|.txt`, `reminder_1h.html|.txt`
- Modify: `app/lessio/web_router.py` — добавить POST endpoint c X-Cron-Token guard
- Test: `tests/test_lessio_web_reminders.py` (4 кейса)

### Steps

- [ ] **Step 1: Failing-test**

```python
"""Cron reminders: 24h + 1h batch dispatch с idempotency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.cron import dispatch_reminders
from app.lessio.models import LessioBooking
from app.lessio.service import (
    auto_onboard_tutor, create_booking, create_services_from_template, create_tutor_profile,
)


async def _book_at(db_session, *, tg_id, slot):
    user, _ = await auto_onboard_tutor(db_session, telegram_user_id=tg_id)
    tutor = await create_tutor_profile(db_session, user=user, slug=f"rem_{tg_id}", display_name="T")
    services = await create_services_from_template(db_session, tutor=tutor, niche="english")
    await db_session.commit()
    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        booking = await create_booking(
            db_session, tutor=tutor, service=services[0], slot=slot,
            client_email="r@e.com", client_full_name="R", client_phone=None,
        )
        await db_session.commit()
    return booking


@patch("app.lessio.cron.send_reminder_email", new_callable=AsyncMock, return_value=True)
async def test_dispatch_24h_sends_for_bookings_in_window(mock_send, db_session) -> None:
    target_slot = datetime.now(UTC) + timedelta(hours=24)
    target_slot = target_slot.replace(microsecond=0)
    booking = await _book_at(db_session, tg_id=60000001, slot=target_slot)

    result = await dispatch_reminders(db_session, hours=24)
    await db_session.commit()
    assert result["sent"] == 1
    refreshed = (await db_session.execute(
        select(LessioBooking).where(LessioBooking.id == booking.id)
    )).scalar_one()
    assert refreshed.reminder_24h_sent_at is not None


@patch("app.lessio.cron.send_reminder_email", new_callable=AsyncMock, return_value=True)
async def test_dispatch_1h_idempotent(mock_send, db_session) -> None:
    target = datetime.now(UTC) + timedelta(minutes=60)
    target = target.replace(microsecond=0)
    await _book_at(db_session, tg_id=60000002, slot=target)

    r1 = await dispatch_reminders(db_session, hours=1)
    await db_session.commit()
    r2 = await dispatch_reminders(db_session, hours=1)
    await db_session.commit()
    assert r1["sent"] == 1
    assert r2["sent"] == 0  # idempotent — second run skips already-flagged


async def test_dispatch_outside_window_no_send(db_session) -> None:
    # Booking on 5 hours from now — should NOT trigger 24h or 1h
    target = datetime.now(UTC) + timedelta(hours=5)
    target = target.replace(microsecond=0)
    await _book_at(db_session, tg_id=60000003, slot=target)

    result24 = await dispatch_reminders(db_session, hours=24)
    result1 = await dispatch_reminders(db_session, hours=1)
    assert result24["sent"] == 0
    assert result1["sent"] == 0


async def test_cron_endpoint_requires_token(client, monkeypatch) -> None:
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "cron_token", "secret123")
    # without header
    r = await client.post("/api/lessio/cron/dispatch-reminders")
    assert r.status_code == 403
    # with wrong
    r = await client.post("/api/lessio/cron/dispatch-reminders",
                          headers={"X-Cron-Token": "wrong"})
    assert r.status_code == 403
    # with correct
    r = await client.post("/api/lessio/cron/dispatch-reminders",
                          headers={"X-Cron-Token": "secret123"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `app/lessio/cron.py`**

```python
"""Lessio cron-driven jobs: reminders 24h + 1h."""

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
    """Send reminder emails for confirmed bookings in (hours-5min, hours+5min) window.

    hours ∈ {1, 24}. Idempotent — UPDATE reminder_{hours}h_sent_at=now() only
    when SMTP returns True.
    """
    now = datetime.now(UTC)
    target = now + timedelta(hours=hours)
    window_start = target - timedelta(minutes=5)
    window_end = target + timedelta(minutes=5)
    field = LessioBooking.reminder_24h_sent_at if hours == 24 else LessioBooking.reminder_1h_sent_at

    bookings = (await session.execute(
        select(LessioBooking).where(
            LessioBooking.status == "confirmed",
            LessioBooking.starts_at >= window_start,
            LessioBooking.starts_at <= window_end,
            field.is_(None),
        )
    )).scalars().all()

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
    _log.info("lessio_reminders_dispatched", hours=hours, sent=sent, failed=failed)
    return {"sent": sent, "failed": failed, "total": len(bookings)}
```

- [ ] **Step 4: Cron endpoint в web_router.py**

```python
import hmac

@router.post("/api/lessio/cron/dispatch-reminders", include_in_schema=False)
async def cron_dispatch_reminders(
    request: Request,
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    from app.config import get_settings
    from app.lessio.cron import dispatch_reminders
    settings = get_settings()
    if not settings.cron_token:
        raise HTTPException(503, "cron не настроен на этом сервере")
    if not x_cron_token or not hmac.compare_digest(x_cron_token, settings.cron_token):
        raise HTTPException(403, "Неверный X-Cron-Token")
    r24 = await dispatch_reminders(session, hours=24)
    r1 = await dispatch_reminders(session, hours=1)
    await session.commit()
    return {"24h": r24, "1h": r1}
```

NB: `prefix="/lessio"` уже на router → endpoint станет `/lessio/api/lessio/cron/dispatch-reminders`. **Поменять** на отдельный router без prefix или вынести cron-endpoint наружу:

```python
# В web_router.py — отдельный router без /lessio prefix:
_cron_router = APIRouter(prefix="/api/lessio", tags=["lessio-cron"])

@_cron_router.post("/cron/dispatch-reminders", ...)  # → /api/lessio/cron/dispatch-reminders

# В нижней части файла:
cron_router = _cron_router
```

И в `main.py`:
```python
from app.lessio.web_router import cron_router as lessio_cron_router
app.include_router(lessio_cron_router)
```

- [ ] **Step 5: reminder_24h.html|.txt + reminder_1h.html|.txt** — копии booking_confirmed.html с другим заголовком («Напоминание: завтра в 14:00» / «Через час встреча»).

- [ ] **Step 6: Lint+tests+commit+push**

```bash
uv run pytest tests/test_lessio_web_reminders.py -v
uv run ruff check && uv run mypy --strict app/ scripts/
uv run pytest -q  # полный suite зелёный
git add -A
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m \
  "Lessio Web MVP chunk 2.4 — cron-reminders 24h+1h + endpoint X-Cron-Token + 4 reminder-templates"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

- [ ] **Step 7: Smoke prod**

```bash
sleep 90  # wait deploy
curl -s https://getdoday.ru/version  # SHA должен совпасть
# С реальным cron token из .env прода — но скорее «cron не настроен» 503 если пусто:
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://getdoday.ru/api/lessio/cron/dispatch-reminders
```

---

## Week 2 — выход

После 4 chunks недели 2:
- ✅ End-to-end booking flow работает: /u/<slug> → /book → submit → emails sent
- ✅ Magic-link manage: клиент видит свои записи + отменяет + переносит
- ✅ Cron reminders 24h+1h каждые 5 мин (как только cron-poll задеплоит)
- ✅ 6 email-шаблонов (booking/new/cancel-2x/reminder-2x) + base shell
- ✅ Полный test suite зелёный, +20 новых тестов

**Что НЕ делает Week 2:**
- Кабинет (Today/Calendar/Clients/Services/Schedule/Income/Settings) — Week 3
- Google Calendar OAuth — Week 3
- CSV-экспорт income — Week 3
- Dynamic OG-image per tutor — SEO chunk Week 3

**После commit'а chunk 2.4 → создать `2026-05-25-lessio-web-mvp-week3.md`** (кабинет + CSV + GC + SEO advanced).

---

## Self-review

**Spec coverage (vs spec F2-F5):**
- ✅ F2 booking-flow (Chunks 2.1+2.2)
- ✅ F3 manage magic-link (Chunk 2.3)
- ✅ F4 reminders cron (Chunk 2.4)
- ✅ F4 event-driven emails (booking_confirmed, new_booking, cancelled) — Chunk 2.1
- ⏳ F5 toggle-payment — Week 3 (cabinet)
- ⏳ F6 Google Calendar — Week 3

**Placeholder scan:** нет TBD.

**Type consistency:** `create_booking` → `LessioBooking`, `cancel_booking` → `LessioBooking`, `reschedule_booking` → `LessioBooking` (новый), `dispatch_reminders` → `dict[str, Any]`.

**Ambiguity:** Cron-poll интервал — spec говорит «каждые 5 мин» но реальный poll каждые 60s. Endpoint idempotent (UPDATE reminder_*_sent_at), так что частый запуск безопасен. Окно ±5 мин ловит booking'и которые попадут точно на granularity poll'а.
