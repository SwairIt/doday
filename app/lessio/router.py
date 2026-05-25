"""Lessio router — landing + waitlist (validation phase).

After validation (≥100 waitlist by 2026-06-01): add /lessio/cabinet/*,
/lessio/book/<slug>, /lessio/api/* per docs/lessio/architecture.md (TBD).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.lessio.models import LessioWaitlistEntry

router = APIRouter(prefix="/lessio", tags=["lessio"])

_templates = Jinja2Templates(directory="app/templates")


# Niches allowed in landing dropdown. Bad values fall back to "other".
_ALLOWED_NICHES: frozenset[str] = frozenset(
    {"english", "ielts", "math", "school", "fitness", "psychology", "yoga", "other"}
)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def lessio_landing(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008 — FastAPI Depends pattern
) -> HTMLResponse:
    """Landing page + waitlist signup form."""
    count_row = await session.execute(select(func.count()).select_from(LessioWaitlistEntry))
    count = int(count_row.scalar_one())
    # Show social proof only after a threshold — empty list signals "no traction"
    show_count = count >= 20
    return _templates.TemplateResponse(
        request,
        "lessio/index.html",
        {
            "waitlist_count": count,
            "show_count": show_count,
        },
    )


@router.post("/waitlist", response_class=HTMLResponse, include_in_schema=False)
async def lessio_submit_waitlist(
    email: Annotated[EmailStr, Form()],
    niche: Annotated[str, Form()],
    pain_point: Annotated[str | None, Form()] = None,
    telegram_handle: Annotated[str | None, Form()] = None,
    source: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008 — FastAPI Depends pattern
) -> HTMLResponse:
    """Accept signup. Idempotent by email — second submit updates the row."""
    safe_niche = niche if niche in _ALLOWED_NICHES else "other"

    existing = (
        await session.execute(select(LessioWaitlistEntry).where(LessioWaitlistEntry.email == email))
    ).scalar_one_or_none()

    if existing is not None:
        if pain_point:
            existing.pain_point = pain_point[:500]
        if telegram_handle:
            existing.telegram_handle = telegram_handle.lstrip("@")[:100]
        existing.niche = safe_niche
        if source:
            existing.source = source[:80]
        await session.commit()
    else:
        entry = LessioWaitlistEntry(
            email=str(email),
            niche=safe_niche,
            pain_point=(pain_point or "")[:500] or None,
            telegram_handle=(telegram_handle or "").lstrip("@")[:100] or None,
            source=(source or "")[:80] or None,
        )
        session.add(entry)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise HTTPException(status_code=500, detail="Не удалось сохранить заявку") from exc

    return HTMLResponse(
        '<div class="rounded-xl bg-emerald-500/15 px-5 py-4 text-emerald-300">'
        "✅ Вы в листе ожидания. Напишу лично в Telegram когда будет первая версия."
        "</div>"
    )
