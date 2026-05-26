"""Lessio cabinet — endpoint'ы под /lessio/app/* для logged-in tutor'ов.

Один router содержит все cabinet-страницы: today / calendar / clients /
services / schedule / income / settings. Все требуют RequiredUser + наличие
LessioTutorProfile (иначе redirect на setup-profile).
"""

from __future__ import annotations

import calendar
import csv as _csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequiredUser
from app.db import get_session
from app.lessio.models import LessioBooking, LessioClient, LessioService, LessioTutorProfile

router = APIRouter(prefix="/lessio/app", tags=["lessio-cabinet"])
_templates = Jinja2Templates(directory="app/templates")


async def _require_profile(session: AsyncSession, user_id: UUID) -> LessioTutorProfile:
    profile = (
        await session.execute(
            select(LessioTutorProfile).where(LessioTutorProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(303, headers={"Location": "/lessio/app/setup-profile"})
    return profile


# ── Today ─────────────────────────────────────────────────────────────


@router.get("/today", response_class=HTMLResponse, include_in_schema=False)
async def today(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    # Считаем границу «сегодня» в зоне tutor'а — иначе UTC-полночь может
    # неправильно отделить вечерние/ночные встречи.
    try:
        tz = ZoneInfo(profile.timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    now_local = datetime.now(tz)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = day_start_local.astimezone(UTC)
    today_end = (day_start_local + timedelta(days=1)).astimezone(UTC)
    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.starts_at >= today_start,
                    LessioBooking.starts_at < today_end,
                    LessioBooking.status == "confirmed",
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )
    # Pre-compute formatted-tz strings (Jinja не должен знать про ZoneInfo)
    booking_views = [
        {
            "obj": b,
            "time_local": _format_in_tz(b.starts_at, profile.timezone, fmt="%H:%M"),
            "tz_label": _format_in_tz(b.starts_at, profile.timezone, fmt="%Z"),
        }
        for b in bookings
    ]
    return _templates.TemplateResponse(
        request,
        "lessio/app/today.html",
        {
            "profile": profile,
            "bookings": bookings,
            "booking_views": booking_views,
            "active_nav": "today",
        },
    )


# ── Settings ──────────────────────────────────────────────────────────


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.config import get_settings as _gs
    from app.lessio.google_calendar import encrypt_refresh_token

    profile = await _require_profile(session, user.id)
    ical_token = encrypt_refresh_token(str(profile.id))
    base = _gs().app_base_url.rstrip("/")
    ical_url = f"{base}/lessio/app/calendar.ics?token={ical_token}"
    return _templates.TemplateResponse(
        request,
        "lessio/app/settings.html",
        {
            "profile": profile,
            "active_nav": "settings",
            "lessio_timezones": _LESSIO_TIMEZONES,
            "ical_url": ical_url,
        },
    )


_SETTINGS_ALLOWED_NICHES: frozenset[str] = frozenset(
    {"english", "ielts", "math", "school", "fitness", "psychology", "yoga", "other"}
)

# Популярные TZ репетиторов РФ/СНГ. Server-side проверка zoneinfo всё равно
# идёт через ZoneInfo(...) — этот список — для UI dropdown.
_LESSIO_TIMEZONES: list[tuple[str, str]] = [
    ("Europe/Kaliningrad", "Калининград (UTC+2)"),
    ("Europe/Moscow", "Москва · Санкт-Петербург (UTC+3)"),
    ("Europe/Samara", "Самара (UTC+4)"),
    ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
    ("Asia/Omsk", "Омск (UTC+6)"),
    ("Asia/Krasnoyarsk", "Красноярск (UTC+7)"),
    ("Asia/Irkutsk", "Иркутск (UTC+8)"),
    ("Asia/Yakutsk", "Якутск (UTC+9)"),
    ("Asia/Vladivostok", "Владивосток (UTC+10)"),
    ("Asia/Magadan", "Магадан (UTC+11)"),
    ("Asia/Kamchatka", "Камчатка (UTC+12)"),
    ("Asia/Almaty", "Алматы (UTC+6)"),
    ("Asia/Tashkent", "Ташкент (UTC+5)"),
    ("Europe/Kyiv", "Киев (UTC+2/+3)"),
    ("Europe/Minsk", "Минск (UTC+3)"),
    ("Europe/Belgrade", "Белград (UTC+1/+2)"),
    ("UTC", "UTC"),
]


def _format_in_tz(dt: datetime, tz_name: str, *, fmt: str) -> str:
    """Format aware UTC datetime в tutor's timezone. Fall back to UTC if invalid."""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return dt.astimezone(tz).strftime(fmt)


@router.post("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_submit(
    request: Request,
    user: RequiredUser,
    slug: Annotated[str, Form()] = "",
    display_name: Annotated[str, Form()] = "",
    niche: Annotated[str, Form()] = "",
    avatar_emoji: Annotated[str, Form()] = "",
    timezone: Annotated[str, Form()] = "",
    bio: Annotated[str | None, Form()] = None,
    default_meeting_url_template: Annotated[str | None, Form()] = None,
    notification_email: Annotated[str | None, Form()] = None,
    booking_lead_hours: Annotated[int, Form()] = 2,
    vacation_until: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.service import validate_slug

    profile = await _require_profile(session, user.id)

    new_slug = (slug or "").strip().lower()
    new_display_name = (display_name or "").strip()
    new_niche = niche if niche in _SETTINGS_ALLOWED_NICHES else profile.niche
    new_emoji = (avatar_emoji or "").strip()[:8] or profile.avatar_emoji
    # Validate timezone via ZoneInfo — invalid keeps current
    new_tz = profile.timezone
    if timezone:
        try:
            ZoneInfo(timezone)
            new_tz = timezone[:64]
        except ZoneInfoNotFoundError:
            pass  # keep current

    slug_changed = False
    if new_slug and new_slug != profile.slug:
        if not validate_slug(new_slug):
            return _templates.TemplateResponse(
                request,
                "lessio/app/settings.html",
                {
                    "profile": profile,
                    "active_nav": "settings",
                    "error": ("slug должен быть 3-50 символов: только латиница/цифры/дефис/_"),
                },
                status_code=400,
            )
        clash = (
            await session.execute(
                select(LessioTutorProfile).where(LessioTutorProfile.slug == new_slug)
            )
        ).scalar_one_or_none()
        if clash is not None and clash.id != profile.id:
            return _templates.TemplateResponse(
                request,
                "lessio/app/settings.html",
                {
                    "profile": profile,
                    "active_nav": "settings",
                    "error": f"slug «{new_slug}» уже занят — выберите другой",
                },
                status_code=400,
            )
        profile.slug = new_slug
        slug_changed = True

    if new_display_name:
        profile.display_name = new_display_name[:100]
    profile.niche = new_niche
    profile.avatar_emoji = new_emoji
    profile.timezone = new_tz
    profile.bio = ((bio or "").strip()[:1000]) or None
    profile.default_meeting_url_template = (
        ((default_meeting_url_template or "").strip()[:500]) or None
    )
    profile.notification_email = ((notification_email or "").strip()[:255]) or None
    # Lead-time + vacation
    if 0 <= booking_lead_hours <= 720:
        profile.booking_lead_hours = booking_lead_hours
    if vacation_until and vacation_until.strip():
        try:
            # HTML datetime-local input format: "2026-06-15T14:00"
            naive = datetime.fromisoformat(vacation_until.strip())
            profile.vacation_until = naive.replace(tzinfo=UTC) if naive.tzinfo is None else naive
        except ValueError:
            pass  # keep current
    else:
        profile.vacation_until = None
    await session.commit()

    if slug_changed:
        from app.config import get_settings as _gs
        from app.lessio.indexnow import ping_indexnow

        base = _gs().app_base_url.rstrip("/")
        await ping_indexnow(urls=[f"{base}/u/{profile.slug}"])

    return RedirectResponse("/lessio/app/settings?toast=saved", status_code=303)


# ── Services CRUD ─────────────────────────────────────────────────────


@router.get("/services", response_class=HTMLResponse, include_in_schema=False)
async def services_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    services = (
        (
            await session.execute(
                select(LessioService)
                .where(LessioService.tutor_id == profile.id)
                .order_by(LessioService.is_active.desc(), LessioService.price_kopecks)
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "lessio/app/services.html",
        {"profile": profile, "services": services, "active_nav": "services"},
    )


@router.post("/services", response_class=HTMLResponse, include_in_schema=False)
async def services_create(
    user: RequiredUser,
    title: Annotated[str, Form()],
    duration_minutes: Annotated[int, Form()],
    price_kopecks: Annotated[int, Form()],
    icon_emoji: Annotated[str, Form()] = "💼",
    is_group_session: Annotated[bool, Form()] = False,
    max_attendees: Annotated[int, Form()] = 1,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    if duration_minutes < 5 or duration_minutes > 480:
        raise HTTPException(400, "Длительность от 5 до 480 минут")
    if price_kopecks < 0:
        raise HTTPException(400, "Цена не может быть отрицательной")
    # Stars = ₽ × 100 / 120 ≈ kopecks / 120. Round to nearest.
    price_stars = max(1, price_kopecks // 120)
    service = LessioService(
        tutor_id=profile.id,
        title=title[:120],
        duration_minutes=duration_minutes,
        price_kopecks=price_kopecks,
        price_stars=price_stars,
        icon_emoji=(icon_emoji or "💼")[:8],
        is_group_session=bool(is_group_session),
        max_attendees=max(1, max_attendees) if is_group_session else 1,
    )
    session.add(service)
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


@router.post(
    "/services/{service_id}/toggle-active",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def services_toggle_active(
    service_id: UUID,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    service = (
        await session.execute(
            select(LessioService).where(
                LessioService.id == service_id,
                LessioService.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    service.is_active = not service.is_active
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


@router.post(
    "/services/{service_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def services_edit(
    service_id: UUID,
    user: RequiredUser,
    title: Annotated[str, Form()],
    duration_minutes: Annotated[int, Form()],
    price_kopecks: Annotated[int, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    service = (
        await session.execute(
            select(LessioService).where(
                LessioService.id == service_id,
                LessioService.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(404, "Услуга не найдена")
    if duration_minutes < 5 or duration_minutes > 480:
        raise HTTPException(400, "Длительность от 5 до 480 минут")
    if price_kopecks < 0:
        raise HTTPException(400, "Цена не может быть отрицательной")
    service.title = title[:120]
    service.duration_minutes = duration_minutes
    service.price_kopecks = price_kopecks
    service.price_stars = max(1, price_kopecks // 120)
    await session.commit()
    return RedirectResponse("/lessio/app/services", status_code=303)


# ── Clients ───────────────────────────────────────────────────────────


@router.get("/clients", response_class=HTMLResponse, include_in_schema=False)
async def clients_page(
    request: Request,
    user: RequiredUser,
    q: str = "",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    clients_q = select(LessioClient).where(LessioClient.tutor_id == profile.id)
    if q.strip():
        from sqlalchemy import or_

        like = f"%{q.strip().lower()}%"
        clients_q = clients_q.where(
            or_(
                LessioClient.full_name.ilike(like),
                LessioClient.email.ilike(like),
                LessioClient.phone.ilike(like),
            )
        )
    clients = (
        (await session.execute(clients_q.order_by(LessioClient.created_at.desc()))).scalars().all()
    )

    # Per-client aggregate: count, total_paid_rub, last_contact
    client_ids = [c.id for c in clients]
    aggregates: dict[UUID, dict[str, int | datetime | None]] = {}
    if client_ids:
        from sqlalchemy import func as _func

        rows = (
            await session.execute(
                select(
                    LessioBooking.client_id,
                    _func.count(LessioBooking.id),
                    _func.coalesce(
                        _func.sum(LessioBooking.price_kopecks).filter(
                            LessioBooking.payment_status == "paid"
                        ),
                        0,
                    ),
                    _func.max(LessioBooking.starts_at),
                )
                .where(LessioBooking.client_id.in_(client_ids))
                .group_by(LessioBooking.client_id)
            )
        ).all()
        for row in rows:
            cid, count, paid_kopecks, last_dt = row
            aggregates[cid] = {
                "bookings_count": int(count or 0),
                "paid_rub": (int(paid_kopecks or 0)) // 100,
                "last_contact": last_dt,
            }

    return _templates.TemplateResponse(
        request,
        "lessio/app/clients.html",
        {
            "profile": profile,
            "clients": clients,
            "aggregates": aggregates,
            "search_query": q,
            "active_nav": "clients",
        },
    )


# ── Schedule (working hours editor) ───────────────────────────────────


@router.get("/schedule", response_class=HTMLResponse, include_in_schema=False)
async def schedule_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    return _templates.TemplateResponse(
        request,
        "lessio/app/schedule.html",
        {
            "profile": profile,
            "active_nav": "schedule",
            "work_start_hour": profile.work_start_minute // 60,
            "work_end_hour": profile.work_end_minute // 60,
        },
    )


@router.post("/schedule", response_class=HTMLResponse, include_in_schema=False)
async def schedule_submit(
    user: RequiredUser,
    working_days: Annotated[list[str], Form()],
    work_start_hour: Annotated[int, Form()],
    work_end_hour: Annotated[int, Form()],
    buffer_minutes: Annotated[int, Form()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    if not (0 <= work_start_hour < work_end_hour <= 24):
        raise HTTPException(400, "Часы начала должны быть меньше часов окончания (0–24)")
    if buffer_minutes < 0 or buffer_minutes > 240:
        raise HTTPException(400, "Буфер от 0 до 240 минут")
    days_parsed = sorted({int(d) for d in working_days if d.isdigit() and 1 <= int(d) <= 7})
    if not days_parsed:
        raise HTTPException(400, "Выберите хотя бы один рабочий день")
    profile.working_days = days_parsed
    profile.work_start_minute = work_start_hour * 60
    profile.work_end_minute = work_end_hour * 60
    profile.buffer_minutes = buffer_minutes
    await session.commit()
    return RedirectResponse("/lessio/app/schedule?toast=saved", status_code=303)


# ── Calendar (month view) ─────────────────────────────────────────────


def _parse_month(s: str | None) -> tuple[int, int]:
    if not s:
        today = datetime.now(UTC)
        return today.year, today.month
    try:
        y, m = s.split("-")
        year, month = int(y), int(m)
        if not (1 <= month <= 12 and 2020 <= year <= 2100):
            raise ValueError
        return year, month
    except (ValueError, AttributeError):
        today = datetime.now(UTC)
        return today.year, today.month


def _parse_iso_date(s: str | None) -> date:
    if not s:
        return datetime.now(UTC).date()
    try:
        return date.fromisoformat(s)
    except ValueError:
        return datetime.now(UTC).date()


@router.get("/calendar", response_class=HTMLResponse, include_in_schema=False)
async def calendar_page(
    request: Request,
    user: RequiredUser,
    month: str | None = None,
    view: str = "month",
    date_param: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    today_utc = datetime.now(UTC).date()

    if view not in {"month", "week", "day"}:
        view = "month"

    if view == "month":
        year, mo = _parse_month(month)
        first = datetime(year, mo, 1, tzinfo=UTC)
        last_day_num = calendar.monthrange(year, mo)[1]
        last = datetime(year, mo, last_day_num, 23, 59, 59, tzinfo=UTC)

        bookings = (
            (
                await session.execute(
                    select(LessioBooking)
                    .where(
                        LessioBooking.tutor_id == profile.id,
                        LessioBooking.starts_at >= first,
                        LessioBooking.starts_at <= last,
                    )
                    .order_by(LessioBooking.starts_at)
                )
            )
            .scalars()
            .all()
        )

        by_day: dict[int, list[LessioBooking]] = {}
        for b in bookings:
            by_day.setdefault(b.starts_at.day, []).append(b)

        first_weekday = first.isoweekday()
        leading_blanks = first_weekday - 1
        days_grid: list[date | None] = [None] * leading_blanks
        for d in range(1, last_day_num + 1):
            days_grid.append(date(year, mo, d))
        while len(days_grid) % 7 != 0:
            days_grid.append(None)

        prev_month = (mo - 1) or 12
        prev_year = year if mo > 1 else year - 1
        next_month = (mo % 12) + 1
        next_year = year if mo < 12 else year + 1
        month_label = f"{year}-{mo:02d}"

        return _templates.TemplateResponse(
            request,
            "lessio/app/calendar.html",
            {
                "profile": profile,
                "active_nav": "calendar",
                "view": "month",
                "year": year,
                "month": mo,
                "month_label": month_label,
                "prev_link": f"/lessio/app/calendar?view=month&month={prev_year}-{prev_month:02d}",
                "next_link": f"/lessio/app/calendar?view=month&month={next_year}-{next_month:02d}",
                "today_link": "/lessio/app/calendar",
                "week_link": f"/lessio/app/calendar?view=week&date_param={today_utc.isoformat()}",
                "day_link": f"/lessio/app/calendar?view=day&date_param={today_utc.isoformat()}",
                "days_grid": days_grid,
                "by_day": by_day,
                "today": today_utc,
            },
        )

    # week / day views — hourly grid
    anchor = _parse_iso_date(date_param)
    if view == "week":
        monday = anchor - timedelta(days=anchor.isoweekday() - 1)
        days = [monday + timedelta(days=i) for i in range(7)]
        prev_anchor = monday - timedelta(days=7)
        next_anchor = monday + timedelta(days=7)
        range_label = (
            f"{monday.strftime('%d.%m')} — {(monday + timedelta(days=6)).strftime('%d.%m.%Y')}"
        )
    else:  # day
        days = [anchor]
        prev_anchor = anchor - timedelta(days=1)
        next_anchor = anchor + timedelta(days=1)
        range_label = anchor.strftime("%A, %d.%m.%Y")

    range_start = datetime.combine(days[0], datetime.min.time(), tzinfo=UTC)
    range_end = datetime.combine(days[-1], datetime.max.time(), tzinfo=UTC)
    bookings_seq = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.starts_at >= range_start,
                    LessioBooking.starts_at <= range_end,
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )
    by_date: dict[date, list[LessioBooking]] = {d: [] for d in days}
    for b in bookings_seq:
        bd = b.starts_at.date()
        if bd in by_date:
            by_date[bd].append(b)

    start_hour = profile.work_start_minute // 60
    end_hour = (profile.work_end_minute + 59) // 60
    if end_hour <= start_hour:
        start_hour, end_hour = 8, 22
    hours = list(range(start_hour, end_hour))

    today_link = f"/lessio/app/calendar?view={view}&date_param={today_utc.isoformat()}"
    prev_link = f"/lessio/app/calendar?view={view}&date_param={prev_anchor.isoformat()}"
    next_link = f"/lessio/app/calendar?view={view}&date_param={next_anchor.isoformat()}"
    month_link = f"/lessio/app/calendar?view=month&month={anchor.year}-{anchor.month:02d}"
    week_link = f"/lessio/app/calendar?view=week&date_param={anchor.isoformat()}"
    day_link = f"/lessio/app/calendar?view=day&date_param={anchor.isoformat()}"

    return _templates.TemplateResponse(
        request,
        "lessio/app/calendar.html",
        {
            "profile": profile,
            "active_nav": "calendar",
            "view": view,
            "range_label": range_label,
            "days": days,
            "hours": hours,
            "by_date": by_date,
            "prev_link": prev_link,
            "next_link": next_link,
            "today_link": today_link,
            "month_link": month_link,
            "week_link": week_link,
            "day_link": day_link,
            "today": today_utc,
        },
    )


# ── Income (paid bookings + CSV export) ───────────────────────────────


async def _month_bookings(
    session: AsyncSession, tutor_id: UUID, year: int, mo: int
) -> list[LessioBooking]:
    first = datetime(year, mo, 1, tzinfo=UTC)
    if mo == 12:
        next_first = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        next_first = datetime(year, mo + 1, 1, tzinfo=UTC)
    return list(
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == tutor_id,
                    LessioBooking.starts_at >= first,
                    LessioBooking.starts_at < next_first,
                    LessioBooking.status.in_(["confirmed", "completed"]),
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )


@router.get("/income", response_class=HTMLResponse, include_in_schema=False)
async def income_page(
    request: Request,
    user: RequiredUser,
    month: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    year, mo = _parse_month(month)
    bookings = await _month_bookings(session, profile.id, year, mo)
    total_paid = sum(b.price_kopecks for b in bookings if b.payment_status == "paid")
    total_unpaid = sum(b.price_kopecks for b in bookings if b.payment_status == "unpaid")
    services = (
        (await session.execute(select(LessioService).where(LessioService.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    service_titles = {s.id: s.title for s in services}
    prev_mo = (mo - 1) or 12
    prev_yr = year if mo > 1 else year - 1
    next_mo = (mo % 12) + 1
    next_yr = year if mo < 12 else year + 1
    return _templates.TemplateResponse(
        request,
        "lessio/app/income.html",
        {
            "profile": profile,
            "active_nav": "income",
            "year": year,
            "month": mo,
            "month_label": f"{year}-{mo:02d}",
            "bookings": bookings,
            "service_titles": service_titles,
            "total_paid_rub": total_paid // 100,
            "total_unpaid_rub": total_unpaid // 100,
            "prev_link": f"/lessio/app/income?month={prev_yr}-{prev_mo:02d}",
            "next_link": f"/lessio/app/income?month={next_yr}-{next_mo:02d}",
            "csv_link": f"/lessio/app/income/export.csv?year={year}&month={mo}",
        },
    )


@router.post(
    "/bookings/{booking_id}/toggle-paid",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def toggle_paid(
    booking_id: UUID,
    user: RequiredUser,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    booking = (
        await session.execute(
            select(LessioBooking).where(
                LessioBooking.id == booking_id,
                LessioBooking.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if booking is None:
        raise HTTPException(404, "Запись не найдена")
    if booking.payment_status == "paid":
        booking.payment_status = "unpaid"
        booking.paid_at = None
        toast = "unpaid"
    else:
        booking.payment_status = "paid"
        booking.paid_at = datetime.now(UTC)
        toast = "paid"
    await session.commit()
    referer = request.headers.get("referer", "/lessio/app/income")
    # Append toast query-param (preserve existing query if any)
    sep = "&" if "?" in referer else "?"
    return RedirectResponse(f"{referer}{sep}toast={toast}", status_code=303)


@router.get(
    "/income/export.csv",
    response_class=Response,
    include_in_schema=False,
)
async def income_export_csv(
    user: RequiredUser,
    year: int,
    month: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    from app.lessio.csv_export import bookings_to_csv

    profile = await _require_profile(session, user.id)
    if not (1 <= month <= 12 and 2020 <= year <= 2100):
        raise HTTPException(400, "Некорректный год/месяц")
    bookings = await _month_bookings(session, profile.id, year, month)
    services = (
        (await session.execute(select(LessioService).where(LessioService.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    service_titles = {s.id: s.title for s in services}
    csv_text = bookings_to_csv(bookings, service_titles=service_titles)
    # UTF-8 BOM — чтобы Excel/Numbers корректно отображал кириллицу
    body = "﻿" + csv_text
    filename = f"lessio_income_{year}-{month:02d}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── PWA: manifest + service worker (для install prompt на mobile) ──────


_PWA_ICON_SVG_DATA = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='%23a78bfa'/><stop offset='1' stop-color='%23f472b6'/>"
    "</linearGradient></defs>"
    "<rect width='192' height='192' rx='36' fill='url(%23g)'/>"
    "<text x='96' y='130' font-size='110' text-anchor='middle' font-family='sans-serif' fill='white'>L</text>"
    "</svg>"
)


@router.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest() -> Response:
    """PWA manifest для добавления Lessio cabinet на homescreen mobile."""
    body = {
        "name": "Lessio",
        "short_name": "Lessio",
        "description": "Кабинет репетитора · Lessio",
        "start_url": "/lessio/app/today",
        "scope": "/lessio/app/",
        "display": "standalone",
        "background_color": "#0f0a1f",
        "theme_color": "#7c3aed",
        "lang": "ru",
        "icons": [
            {"src": _PWA_ICON_SVG_DATA, "sizes": "192x192", "type": "image/svg+xml"},
            {"src": _PWA_ICON_SVG_DATA, "sizes": "512x512", "type": "image/svg+xml"},
        ],
    }
    import json

    return Response(
        content=json.dumps(body, ensure_ascii=False),
        media_type="application/manifest+json",
    )


_SW_JS = """\
// Lessio cabinet service-worker — network-first с offline fallback.
const CACHE = 'lessio-cab-v1';

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });

self.addEventListener('fetch', e => {
  // Only handle GET requests under /lessio/app/
  if (e.request.method !== 'GET' || !e.request.url.includes('/lessio/app/')) return;
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
"""


@router.get("/sw.js", include_in_schema=False)
async def pwa_service_worker() -> Response:
    return Response(content=_SW_JS, media_type="application/javascript; charset=utf-8")


# ── Stats dashboard ───────────────────────────────────────────────────


@router.get("/stats", response_class=HTMLResponse, include_in_schema=False)
async def stats_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    # Все non-cancelled bookings — для total counts + revenue
    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.status.in_(["confirmed", "completed"]),
                )
                .order_by(LessioBooking.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )
    services = (
        (await session.execute(select(LessioService).where(LessioService.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    service_titles = {s.id: s.title for s in services}

    total_count = len(bookings)
    total_earned = sum(b.price_kopecks for b in bookings if b.payment_status == "paid") // 100
    total_pending = sum(b.price_kopecks for b in bookings if b.payment_status != "paid") // 100

    # Aggregate by service (count + revenue)
    by_service: dict[str, dict[str, int]] = {}
    for b in bookings:
        title = service_titles.get(b.service_id, "—")
        bucket = by_service.setdefault(title, {"count": 0, "revenue_rub": 0})
        bucket["count"] += 1
        if b.payment_status == "paid":
            bucket["revenue_rub"] += b.price_kopecks // 100
    service_breakdown: list[dict[str, int | str]] = sorted(
        [
            {"title": t, "count": v["count"], "revenue_rub": v["revenue_rub"]}
            for t, v in by_service.items()
        ],
        key=lambda d: -int(d["count"]),
    )

    # Last 30d count (rough conversion proxy)
    now = datetime.now(UTC)
    last_30d = sum(1 for b in bookings if b.starts_at >= now - timedelta(days=30))

    return _templates.TemplateResponse(
        request,
        "lessio/app/stats.html",
        {
            "profile": profile,
            "active_nav": "stats",
            "total_count": total_count,
            "total_earned": total_earned,
            "total_pending": total_pending,
            "service_breakdown": service_breakdown,
            "last_30d": last_30d,
        },
    )


# ── iCal feed (tutor subscribes in native calendar) ──────────────────


@router.get("/calendar.ics", include_in_schema=False)
async def ical_feed(
    token: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """RFC5545 iCal feed для tutor'а. Token = encrypted profile.id."""
    from uuid import UUID as _UUID

    from app.config import get_settings as _gs
    from app.lessio.google_calendar import decrypt_refresh_token
    from app.lessio.ical_export import bookings_to_ical

    if not token:
        raise HTTPException(404)
    decrypted = decrypt_refresh_token(token)
    if not decrypted:
        raise HTTPException(404)
    try:
        profile_id = _UUID(decrypted)
    except ValueError as exc:
        raise HTTPException(404) from exc
    profile = await session.get(LessioTutorProfile, profile_id)
    if profile is None:
        raise HTTPException(404)

    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(
                    LessioBooking.tutor_id == profile.id,
                    LessioBooking.status.in_(["confirmed", "completed"]),
                )
                .order_by(LessioBooking.starts_at)
            )
        )
        .scalars()
        .all()
    )
    services = (
        (await session.execute(select(LessioService).where(LessioService.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    service_titles = {s.id: s.title for s in services}

    base_url = _gs().app_base_url.rstrip("/")
    body = bookings_to_ical(
        tutor=profile,
        bookings=bookings,
        service_titles=service_titles,
        base_url=base_url,
    )
    return Response(content=body, media_type="text/calendar; charset=utf-8")


# ── Bulk CSV import ───────────────────────────────────────────────────


@router.get("/clients/import", response_class=HTMLResponse, include_in_schema=False)
async def clients_import_page(
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    return _templates.TemplateResponse(
        request,
        "lessio/app/clients_import.html",
        {"profile": profile, "active_nav": "clients"},
    )


@router.post("/clients/import", response_class=HTMLResponse, include_in_schema=False)
async def clients_import_submit(
    request: Request,
    user: RequiredUser,
    csv: Annotated[UploadFile, File()],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    raw = (await csv.read()).decode("utf-8-sig", errors="replace")
    reader = _csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "email" not in {
        (f or "").strip().lower() for f in reader.fieldnames
    }:
        return _templates.TemplateResponse(
            request,
            "lessio/app/clients_import.html",
            {
                "profile": profile,
                "active_nav": "clients",
                "error": (
                    "В CSV не найдена колонка 'email' — она обязательна. "
                    "Минимальный формат: email,full_name,phone"
                ),
            },
            status_code=400,
        )

    created = 0
    updated = 0
    skipped = 0
    for row in reader:
        # Normalize keys to lowercase
        row_norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = row_norm.get("email", "").lower()
        full_name = row_norm.get("full_name") or row_norm.get("name", "")
        phone = row_norm.get("phone") or None
        if not email or "@" not in email:
            skipped += 1
            continue
        existing = (
            await session.execute(
                select(LessioClient).where(
                    LessioClient.tutor_id == profile.id,
                    LessioClient.email == email,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if full_name:
                existing.full_name = full_name[:120]
            if phone:
                existing.phone = phone[:50]
            updated += 1
        else:
            client = LessioClient(
                tutor_id=profile.id,
                email=email[:255],
                full_name=(full_name or email)[:120],
                phone=(phone or None) and phone[:50],
                telegram_user_id=None,
            )
            session.add(client)
            created += 1
    await session.commit()
    return RedirectResponse(
        f"/lessio/app/clients?toast=imported&created={created}&updated={updated}&skipped={skipped}",
        status_code=303,
    )


@router.get("/clients/{client_id}", response_class=HTMLResponse, include_in_schema=False)
async def client_detail(
    client_id: UUID,
    request: Request,
    user: RequiredUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    profile = await _require_profile(session, user.id)
    client = (
        await session.execute(
            select(LessioClient).where(
                LessioClient.id == client_id,
                LessioClient.tutor_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    bookings = (
        (
            await session.execute(
                select(LessioBooking)
                .where(LessioBooking.client_id == client.id)
                .order_by(LessioBooking.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )
    # Aggregate stats
    completed_or_confirmed = [b for b in bookings if b.status in ("confirmed", "completed")]
    paid_rub = sum(b.price_kopecks for b in bookings if b.payment_status == "paid") // 100
    unpaid_rub = (
        sum(
            b.price_kopecks
            for b in bookings
            if b.payment_status != "paid" and b.status != "cancelled"
        )
        // 100
    )
    avg_rub = (
        (sum(b.price_kopecks for b in completed_or_confirmed) // 100 // len(completed_or_confirmed))
        if completed_or_confirmed
        else 0
    )

    return _templates.TemplateResponse(
        request,
        "lessio/app/client_detail.html",
        {
            "profile": profile,
            "client": client,
            "bookings": bookings,
            "stats": {
                "total_bookings": len(bookings),
                "completed_count": sum(1 for b in bookings if b.status == "completed"),
                "upcoming_count": sum(1 for b in bookings if b.status == "confirmed"),
                "cancelled_count": sum(1 for b in bookings if b.status == "cancelled"),
                "paid_rub": paid_rub,
                "unpaid_rub": unpaid_rub,
                "avg_rub": avg_rub,
            },
            "active_nav": "clients",
        },
    )
