"""HTTP routes for complaints + admin panel + token-secured Claude access.

Public-ish:
- POST /api/complaints — logged-in user submits a complaint.

Admin (RequiredAdmin → users.is_admin = True):
- GET /api/admin/complaints?status=&priority=&since=&limit=
- PATCH /api/admin/complaints/{id} — change status/priority/admin_note.
- DELETE /api/admin/complaints/{id}
- GET /api/admin/stats — dashboard numbers.

Token-secured (X-Admin-Token == settings.admin_token):
- GET /api/admin/complaints.json — same as /api/admin/complaints but
  authorised by header instead of cookie. So Claude can curl it.
"""

import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.admin.schemas import ComplaintAdminPatch, ComplaintIn, ComplaintOut
from app.admin.service import (
    create_complaint,
    delete_complaint,
    list_complaints,
    update_complaint,
)
from app.auth.deps import DbSession, RequiredAdmin, RequiredUser
from app.config import get_settings


def _parse_since(since: str | None) -> datetime | None:
    """Accept 'today', 'week', or ISO-8601 timestamp. Return UTC datetime or None."""
    if not since:
        return None
    if since == "today":
        return datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
    if since == "week":
        return datetime.now(UTC) - timedelta(days=7)
    if since == "month":
        return datetime.now(UTC) - timedelta(days=30)
    try:
        dt = datetime.fromisoformat(since)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "since: bad format") from e


# ---- Public-ish: any signed-in user can submit a complaint ------------------

complaints_router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@complaints_router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    payload: ComplaintIn,
    user: RequiredUser,
    session: DbSession,
) -> ComplaintOut:
    """Юзер отправляет жалобу из help-drawer. Привязка к user_id обязательна."""
    c = await create_complaint(
        session,
        user_id=user.id,
        body=payload.body,
        page_url=payload.page_url,
        viewport=payload.viewport,
        user_agent=payload.user_agent,
    )
    return ComplaintOut.model_validate(c)


# ---- Admin: requires users.is_admin = True ---------------------------------

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class StarPaymentAdminOut(BaseModel):
    """Admin-facing payment row — includes user_id and refund affordance."""

    id: UUID
    user_id: UUID
    user_email: str
    product_code: str
    stars_amount: int
    status: str
    created_at: datetime
    refunded_at: datetime | None
    refund_reason: str | None
    telegram_payment_charge_id: str


@admin_router.get("/billing/payments", response_model=list[StarPaymentAdminOut])
async def admin_list_payments(
    _: RequiredAdmin,
    session: DbSession,
    limit: int = 200,
) -> list[StarPaymentAdminOut]:
    """All Stars payments across all users — for revenue inspection + refund."""
    from sqlalchemy import desc as sa_desc
    from sqlalchemy import select as sa_select

    from app.auth.models import User as _User
    from app.billing.models import StarPayment

    rows = await session.execute(
        sa_select(StarPayment, _User.email)
        .join(_User, _User.id == StarPayment.user_id)
        .order_by(sa_desc(StarPayment.created_at))
        .limit(min(max(limit, 1), 500))
    )
    out: list[StarPaymentAdminOut] = []
    for p, email in rows.all():
        out.append(
            StarPaymentAdminOut(
                id=p.id,
                user_id=p.user_id,
                user_email=email,
                product_code=p.product_code,
                stars_amount=p.stars_amount,
                status=p.status,
                created_at=p.created_at,
                refunded_at=p.refunded_at,
                refund_reason=p.refund_reason,
                telegram_payment_charge_id=p.telegram_payment_charge_id,
            )
        )
    return out


class RefundPayload(BaseModel):
    reason: str | None = None


@admin_router.post("/billing/payments/{payment_id}/refund")
async def admin_refund_payment(
    payment_id: UUID,
    payload: RefundPayload,
    _: RequiredAdmin,
    session: DbSession,
) -> dict[str, object]:
    """Refund a Stars payment via Bot API + roll back user.pro_until.

    Telegram's 21-day window applies — older charges return ok:False from the
    Bot API and we keep the row as paid (admin can re-try later or follow up
    with the user manually).
    """
    from app.billing.models import StarPayment
    from app.billing.stars import StarsError, refund_payment

    p = await session.get(StarPayment, payment_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "платёж не найден")
    try:
        ok = await refund_payment(session, p, reason=payload.reason)
    except StarsError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    await session.commit()
    return {"ok": ok, "status": p.status}


@admin_router.get("/complaints", response_model=list[ComplaintOut])
async def admin_list_complaints(
    _: RequiredAdmin,
    session: DbSession,
    status_filter: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    limit: int = 200,
) -> list[ComplaintOut]:
    rows = await list_complaints(
        session,
        status_filter=status_filter,
        priority_filter=priority,
        since=_parse_since(since),
        limit=min(max(limit, 1), 500),
    )
    return [ComplaintOut.model_validate(c) for c in rows]


@admin_router.patch("/complaints/{complaint_id}", response_model=ComplaintOut)
async def admin_patch_complaint(
    complaint_id: UUID,
    payload: ComplaintAdminPatch,
    _: RequiredAdmin,
    session: DbSession,
) -> ComplaintOut:
    c = await update_complaint(
        session,
        complaint_id,
        status=payload.status,
        priority=payload.priority,
        admin_note=payload.admin_note,
    )
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")
    return ComplaintOut.model_validate(c)


@admin_router.delete("/complaints/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_complaint(
    complaint_id: UUID,
    _: RequiredAdmin,
    session: DbSession,
) -> None:
    if not await delete_complaint(session, complaint_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")


# ---- Token-secured for Claude (curl-friendly without cookies) ---------------

token_router = APIRouter(prefix="/api/admin", tags=["admin"])


@token_router.get("/complaints.json", response_model=list[ComplaintOut])
async def admin_complaints_via_token(
    session: DbSession,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    status_filter: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    limit: int = 200,
) -> list[ComplaintOut]:
    """Same as /api/admin/complaints but auth via X-Admin-Token. For Claude
    to fetch when юзер скажет «посмотри жалобы за сегодня»."""
    settings = get_settings()
    if not settings.admin_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ADMIN_TOKEN не задан в окружении — endpoint отключён",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid admin token")
    rows = await list_complaints(
        session,
        status_filter=status_filter,
        priority_filter=priority,
        since=_parse_since(since),
        limit=min(max(limit, 1), 500),
    )
    return [ComplaintOut.model_validate(c) for c in rows]
