# Lessio Web MVP — Week 3: Кабинет + CSV income + SEO advanced + production-ready

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) или superpowers:subagent-driven-development. Шаги checkbox (`- [ ]`).

**Goal:** Полноценный кабинет репетитора — Today/Calendar/Clients/Services/Schedule/Settings + Income (с toggle-paid + CSV экспортом). Plus SEO-полировка (dynamic per-tutor OG-image SVG + aggregateOffer JSON-LD). К концу Wk3 — production-ready: README + ENV.example обновлены, smoke-test расширен, PROGRESS закрыт. Google Calendar OAuth — deferred в Phase 2 (тяжёлый OAuth-flow + Fernet encryption + heavy testing).

**Architecture:** Cabinet shell — Jinja2 base template (`templates/lessio/app/_base.html`) с sidebar nav, наследуется всеми кабинет-страницами. CRUD ресурсов идёт через HTMX-friendly endpoints + редко обновляемые формы. CSV export — streaming `Response(content=...)` с `Content-Disposition: attachment`. Toggle paid — POST `/lessio/app/bookings/<id>/toggle-paid` через HTMX.

**Tech Stack:** Python 3.12 / FastAPI / async SQLAlchemy / Jinja2 / HTMX / Tailwind CDN / Alpine.js (только slot-picker, остальное native).

**Spec:** [`docs/superpowers/specs/2026-05-25-lessio-web-mvp-design.md`](../specs/2026-05-25-lessio-web-mvp-design.md) (F5 toggle-payment, кабинет, CSV)

**Wk2 baseline (prod SHA 52523f0):** ✅ Booking flow живой, ✅ magic-link manage работает, ✅ cron reminders задеплоены, ✅ 6 email-шаблонов готовы.

---

## File Structure (week 3)

**Create:**
- `app/lessio/cabinet_router.py` — отдельный router с prefix `/lessio/app/` для cabinet endpoints (расширяем `/today` placeholder, добавляем все остальные)
- `app/lessio/csv_export.py` — `export_income_csv(tutor, year, month) -> str`
- `app/lessio/og_image.py` — dynamic per-tutor SVG OG generator (бесплатно, без headless browser)
- `app/templates/lessio/app/_base.html` — sidebar shell
- `app/templates/lessio/app/today.html` — список сегодняшних встреч
- `app/templates/lessio/app/calendar.html` — month-view с цветными слотами
- `app/templates/lessio/app/clients.html` + `client_detail.html`
- `app/templates/lessio/app/services.html` + form modals
- `app/templates/lessio/app/schedule.html` — working hours editor
- `app/templates/lessio/app/income.html` — sum-by-month + CSV кнопка
- `app/templates/lessio/app/settings.html` — bio/meeting_url/notification_email editor
- `tests/test_lessio_web_cabinet_today.py` — 3 кейса
- `tests/test_lessio_web_cabinet_settings.py` — 3 кейса
- `tests/test_lessio_web_cabinet_services.py` — 4 кейса (create/edit/toggle/delete)
- `tests/test_lessio_web_cabinet_clients.py` — 3 кейса
- `tests/test_lessio_web_cabinet_schedule.py` — 3 кейса
- `tests/test_lessio_web_cabinet_calendar.py` — 2 кейса
- `tests/test_lessio_web_cabinet_income.py` — 4 кейса (toggle paid + CSV)
- `tests/test_lessio_web_og_image.py` — 3 кейса (render + sanitize)

**Modify:**
- `app/main.py` — register cabinet_router + add `/u/<slug>/og.svg` route for dynamic OG-image
- `app/lessio/web_router.py` — заменить inline-HTML placeholder `/lessio/app/today` на redirect к новому router'у (или просто удалить — `cabinet_router` overrides)
- `app/templates/lessio/u/profile.html` — поменять `og:image` на per-tutor `/u/<slug>/og.svg`
- `README.md` — добавить Lessio overview + URL-map + dev-команды
- `ENV.example` — добавить SMTP_FROM/CRON_TOKEN если ещё не указаны
- `PROGRESS.md` — финальный summary, Week 3 закрыт, что осталось в Phase 2

---

## Chunk 3.1: Cabinet shell + Today page + Settings

**Files:**
- Create: `app/lessio/cabinet_router.py`
- Create: `app/templates/lessio/app/_base.html` (sidebar shell)
- Create: `app/templates/lessio/app/today.html`
- Create: `app/templates/lessio/app/settings.html`
- Modify: `app/lessio/web_router.py` — удалить inline placeholder (cabinet_router заменит)
- Modify: `app/main.py` — register cabinet_router
- Test: `tests/test_lessio_web_cabinet_today.py` + `tests/test_lessio_web_cabinet_settings.py`

### Steps

- [ ] **Step 1: Failing-tests (today + settings)**

```python
# tests/test_lessio_web_cabinet_today.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.service import (
    auto_onboard_tutor, create_booking, create_services_from_template, create_tutor_profile,
)


async def _logged_tutor(client, db_session, *, tg_id=70000001):
    # Регистрируем через web-flow, чтобы появилась session-cookie
    await client.post("/lessio/auth/register",
                      data={"email": f"t{tg_id}@e.com", "password": "strongpass123"},
                      follow_redirects=False)
    await client.post("/lessio/app/setup-profile",
                      data={"slug": f"today_{tg_id}", "display_name": "T", "niche": "english"},
                      follow_redirects=False)
    return None


async def test_today_redirects_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/lessio/app/today", follow_redirects=False)
    assert resp.status_code in (401, 303, 302)


async def test_today_shows_upcoming_bookings(client: AsyncClient, db_session) -> None:
    await _logged_tutor(client, db_session, tg_id=70000002)
    from app.auth.models import User
    from sqlalchemy import select
    from app.lessio.models import LessioTutorProfile, LessioService
    user = (await db_session.execute(
        select(User).where(User.email == "t70000002@e.com")
    )).scalar_one()
    tutor = (await db_session.execute(
        select(LessioTutorProfile).where(LessioTutorProfile.user_id == user.id)
    )).scalar_one()
    service = (await db_session.execute(
        select(LessioService).where(LessioService.tutor_id == tutor.id)
    )).scalars().first()

    with patch("app.lessio.service.send_booking_emails", new_callable=AsyncMock):
        today_slot = datetime.now(UTC).replace(hour=14, minute=0, second=0, microsecond=0)
        await create_booking(
            db_session, tutor=tutor, service=service, slot=today_slot,
            client_email="c@e.com", client_full_name="Customer", client_phone=None,
        )
        await db_session.commit()

    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    assert "Customer" in resp.text


async def test_today_empty_state(client: AsyncClient, db_session) -> None:
    await _logged_tutor(client, db_session, tg_id=70000003)
    resp = await client.get("/lessio/app/today")
    assert resp.status_code == 200
    assert "сегодня" in resp.text.lower() or "пока нет" in resp.text.lower()


# tests/test_lessio_web_cabinet_settings.py
async def test_settings_page_renders(client, db_session) -> None:
    await _logged_tutor(client, db_session, tg_id=71000001)
    resp = await client.get("/lessio/app/settings")
    assert resp.status_code == 200
    assert 'name="bio"' in resp.text
    assert 'name="default_meeting_url_template"' in resp.text


async def test_settings_post_updates_profile(client, db_session) -> None:
    await _logged_tutor(client, db_session, tg_id=71000002)
    resp = await client.post(
        "/lessio/app/settings",
        data={
            "bio": "Новое био",
            "default_meeting_url_template": "https://zoom.us/j/123",
            "notification_email": "notify@e.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    # Re-fetch and verify
    from sqlalchemy import select
    from app.lessio.models import LessioTutorProfile
    profile = (await db_session.execute(
        select(LessioTutorProfile).where(LessioTutorProfile.slug == "today_71000002")
    )).scalar_one()
    assert profile.bio == "Новое био"
    assert profile.default_meeting_url_template == "https://zoom.us/j/123"
    assert profile.notification_email == "notify@e.com"


async def test_settings_unauth_redirects(client) -> None:
    resp = await client.get("/lessio/app/settings", follow_redirects=False)
    assert resp.status_code in (401, 302, 303)
```

- [ ] **Step 2: Create `app/lessio/cabinet_router.py`**

```python
"""Lessio cabinet — все endpoint'ы под /lessio/app/ для logged-in tutor'ов."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequiredUser
from app.db import get_session
from app.lessio.models import LessioBooking, LessioClient, LessioService, LessioTutorProfile

router = APIRouter(prefix="/lessio/app", tags=["lessio-cabinet"])
_templates = Jinja2Templates(directory="app/templates")


async def _require_profile(
    session: AsyncSession, user_id: UUID
) -> LessioTutorProfile:
    profile = (await session.execute(
        select(LessioTutorProfile).where(LessioTutorProfile.user_id == user_id)
    )).scalar_one_or_none()
    if profile is None:
        raise HTTPException(303, headers={"Location": "/lessio/app/setup-profile"})
    return profile


@router.get("/today", response_class=HTMLResponse, include_in_schema=False)
async def today(
    request: Request, user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    bookings = (await session.execute(
        select(LessioBooking).where(
            LessioBooking.tutor_id == profile.id,
            LessioBooking.starts_at >= today_start,
            LessioBooking.starts_at < today_end,
            LessioBooking.status == "confirmed",
        ).order_by(LessioBooking.starts_at)
    )).scalars().all()
    return _templates.TemplateResponse(
        request, "lessio/app/today.html",
        {"profile": profile, "bookings": bookings, "active_nav": "today"},
    )


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(
    request: Request, user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    return _templates.TemplateResponse(
        request, "lessio/app/settings.html",
        {"profile": profile, "active_nav": "settings"},
    )


@router.post("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_submit(
    user: RequiredUser,
    bio: Annotated[str | None, Form()] = None,
    default_meeting_url_template: Annotated[str | None, Form()] = None,
    notification_email: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    profile.bio = (bio or "").strip()[:1000] or None
    profile.default_meeting_url_template = (default_meeting_url_template or "").strip()[:500] or None
    profile.notification_email = (notification_email or "").strip()[:255] or None
    await session.commit()
    return RedirectResponse("/lessio/app/settings?saved=1", status_code=303)
```

- [ ] **Step 3: Create `app/templates/lessio/app/_base.html`** — Tailwind shell с sidebar

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}Lessio · Кабинет{% endblock %}</title>
  <meta name="robots" content="noindex,nofollow">
  <link rel="icon" href="/favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background:linear-gradient(180deg,#0f0a1f,#1a0f3d 60%,#2e1065);
           color:#f5f3ff; min-height:100vh;
           font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
    .nav-link { display:block; padding:.6rem .9rem; border-radius:.6rem;
                color:rgba(245,243,255,.6); transition:background .1s; }
    .nav-link:hover { background:rgba(255,255,255,.05); color:rgba(245,243,255,.9); }
    .nav-link.active { background:rgba(167,139,250,.15); color:#a78bfa; }
  </style>
</head>
<body class="antialiased">
<div class="md:grid md:grid-cols-[220px_1fr] min-h-screen">
  <aside class="border-r border-white/5 p-4 bg-black/20">
    <a href="/lessio" class="block text-xl font-extrabold mb-6">
      <span style="background:linear-gradient(135deg,#a78bfa,#f472b6);-webkit-background-clip:text;background-clip:text;color:transparent;">
        ✦ Lessio
      </span>
    </a>
    <nav class="space-y-1 text-sm">
      <a href="/lessio/app/today" class="nav-link {% if active_nav == 'today' %}active{% endif %}">📅 Сегодня</a>
      <a href="/lessio/app/calendar" class="nav-link {% if active_nav == 'calendar' %}active{% endif %}">📆 Календарь</a>
      <a href="/lessio/app/clients" class="nav-link {% if active_nav == 'clients' %}active{% endif %}">👥 Клиенты</a>
      <a href="/lessio/app/services" class="nav-link {% if active_nav == 'services' %}active{% endif %}">💼 Услуги</a>
      <a href="/lessio/app/schedule" class="nav-link {% if active_nav == 'schedule' %}active{% endif %}">⏰ Расписание</a>
      <a href="/lessio/app/income" class="nav-link {% if active_nav == 'income' %}active{% endif %}">💰 Доход</a>
      <a href="/lessio/app/settings" class="nav-link {% if active_nav == 'settings' %}active{% endif %}">⚙️ Настройки</a>
    </nav>
    <div class="mt-8 px-3 py-2 bg-white/5 rounded-lg text-xs">
      Публичная ссылка:<br>
      <a href="/u/{{ profile.slug }}" class="text-violet-300 break-all">/u/{{ profile.slug }}</a>
    </div>
  </aside>

  <main class="p-6 md:p-10 max-w-5xl">
    {% block content %}{% endblock %}
  </main>
</div>
</body>
</html>
```

- [ ] **Step 4: `today.html` + `settings.html`** (см. plan body)

- [ ] **Step 5: Удалить inline placeholder из `web_router.py`** — функция `lessio_today_placeholder` заменяется cabinet_router.today (FastAPI router resolution — последний зарегистрированный с тем же путём wins; чтобы избежать confusion, удаляем placeholder + import).

- [ ] **Step 6: Register cabinet_router в `app/main.py`**

- [ ] **Step 7: Run tests + lint + commit + push**

---

## Chunk 3.2: Services CRUD + Clients pages

**Files:**
- Modify: `app/lessio/cabinet_router.py` — добавить /services CRUD + /clients
- Create: `app/templates/lessio/app/services.html` + `app/templates/lessio/app/clients.html`
- Create: `app/templates/lessio/app/client_detail.html`
- Test: `tests/test_lessio_web_cabinet_services.py` (4) + `tests/test_lessio_web_cabinet_clients.py` (3)

Структура endpoints:
- `GET  /lessio/app/services` — list + inline-form для добавления
- `POST /lessio/app/services` — create
- `POST /lessio/app/services/<id>/toggle-active` — soft-delete
- `POST /lessio/app/services/<id>/edit` — обновить title/duration/price
- `GET  /lessio/app/clients` — list (filter by email search)
- `GET  /lessio/app/clients/<id>` — detail с историей bookings

---

## Chunk 3.3: Schedule editor + Calendar month view

**Files:**
- Modify: `app/lessio/cabinet_router.py` — /schedule + /calendar
- Create: `app/templates/lessio/app/schedule.html` (working_days checkboxes + work_start/end_minute sliders/inputs + buffer)
- Create: `app/templates/lessio/app/calendar.html` (month grid)
- Test: 3 schedule + 2 calendar

`/lessio/app/calendar?month=YYYY-MM` — простой grid 7×N с цветными цветными слотами (confirmed=violet, cancelled=gray, completed=emerald).

---

## Chunk 3.4: Income + CSV export + SEO advanced (dynamic OG-image)

**Files:**
- Modify: `app/lessio/cabinet_router.py` — /income + POST /bookings/<id>/toggle-paid + GET /income/export.csv
- Create: `app/lessio/csv_export.py` — pure function `bookings_to_csv(bookings, year, month) -> str` (year/month опционально)
- Create: `app/lessio/og_image.py` — `render_tutor_og_svg(tutor: LessioTutorProfile) -> bytes` — SVG-template с подставленным display_name + avatar_emoji + niche
- Modify: `app/main.py` — add GET `/u/<slug>/og.svg` (cache-control: 1 day)
- Modify: `app/templates/lessio/u/profile.html` — `og:image` → `/u/<slug>/og.svg`
- Test: `tests/test_lessio_web_cabinet_income.py` (4 — toggle paid, CSV header/content, filter by month, total sum)
- Test: `tests/test_lessio_web_og_image.py` (3 — render valid SVG, escapes special chars, 404 for unknown)

CSV format:
```
date,client_name,client_email,service,duration_min,price_rub,paid
2026-05-10,Иван Петров,ivan@e.com,Английский · 60 мин,60,1500,paid
2026-05-12,Анна Сидорова,anna@e.com,IELTS подготовка,90,2500,unpaid
```

OG-image SVG (1200×630, Tailwind colors):
```python
def render_tutor_og_svg(tutor) -> bytes:
    # Inline SVG с background gradient + большой emoji + display_name + niche
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0f0a1f"/><stop offset="1" stop-color="#2e1065"/>
  </linearGradient></defs>
  <rect width="1200" height="630" fill="url(#g)"/>
  <text x="600" y="240" font-family="-apple-system,sans-serif" font-size="120" text-anchor="middle">{escape(tutor.avatar_emoji)}</text>
  <text x="600" y="380" font-family="-apple-system,sans-serif" font-size="64" font-weight="800" fill="#fff" text-anchor="middle">{escape(tutor.display_name[:32])}</text>
  <text x="600" y="450" font-family="-apple-system,sans-serif" font-size="32" fill="#a78bfa" text-anchor="middle">{NICHE_LABELS.get(tutor.niche, 'Преподаватель')}</text>
  <text x="600" y="560" font-family="-apple-system,sans-serif" font-size="24" fill="rgba(255,255,255,.4)" text-anchor="middle">Lessio · getdoday.ru</text>
</svg>""".encode("utf-8")
```

- [ ] **Wrap-up Steps в конце chunk'а 3.4:**

- README.md — добавить блок «Lessio Web» с URL-map + dev-команды
- ENV.example — убедиться что SMTP_FROM + CRON_TOKEN документированы
- PROGRESS.md — финальный summary: Week 3 закрыт, что осталось в Phase 2 (Google Calendar, embedded payments, mobile PWA tweaks)

---

## Week 3 — выход

После 4 chunks:
- ✅ Полный кабинет (7 страниц): Today / Calendar / Clients / Services / Schedule / Income / Settings
- ✅ CSV экспорт income для самозанятого учёта (Мой Налог импорт)
- ✅ Toggle-paid в карточке клиента + календаре
- ✅ Dynamic per-tutor OG-image (бесплатный SVG, без headless browser)
- ✅ README + ENV.example + PROGRESS обновлены — repo onboardable

**Production-ready после всех 3 недель.**

**Что НЕ делает Week 3 → Phase 2:**
- Google Calendar OAuth (heavy: Fernet encryption + refresh-token rotation + busy-times API)
- Embedded payments (ЮKassa requires 18+, Stars — нет смысла за пределами TG-flow)
- Aggregate rating в JSON-LD (нужны отзывы от клиентов — отдельная фича)
- Sitemap ping (notify Google/Yandex on tutor signup) — IndexNow API
- Multi-language (только RU в MVP)
- Mobile PWA install prompt
- Search/discovery /lessio/discover — нужен scale (≥50 репетиторов)

---

## Self-review

**Spec coverage (Phase 1 MVP):**
- ✅ F1 Onboarding (Wk1)
- ✅ F2 Booking (Wk2)
- ✅ F3 Manage magic-link (Wk2)
- ✅ F4 Reminders (Wk2)
- ✅ F5 Toggle-payment (Wk3)
- ⏳ F6 Google Calendar — Phase 2

**Placeholder scan:** нет TBD.

**Type consistency:** все cabinet_router endpoint'ы возвращают `Response`, settings_submit — `Response` (redirect). CSV-export — `str` (encoded на router level).
