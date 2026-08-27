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
from pydantic import BaseModel, Field

from app.admin.models import Complaint
from app.admin.schemas import ComplaintAdminPatch, ComplaintIn, ComplaintOut
from app.admin.service import (
    create_complaint,
    delete_complaint,
    get_complaint,
    list_complaints,
    purge_unverified,
    update_complaint,
)
from app.auth.deps import DbSession, RequiredAdmin, RequiredUser
from app.config import get_settings


async def _notify_complaint_author(
    session: DbSession,
    complaint: Complaint,
    *,
    kind: str,
    title: str,
    body: str,
    subject: str,
    email_when_inapp: bool,
) -> None:
    """Уведомляет автора обращения по доступным каналам.

    Зарегистрированному — колокольчик в приложении; анониму (и, при
    ``email_when_inapp``, зарегистрированному тоже) — письмо на оставленную почту.
    Оба канала best-effort: сбой одного не мешает другому и не роняет запрос.
    """
    import logging

    has_inapp = False
    if complaint.user_id is not None:
        try:
            from app.notifications.service import create_notification

            await create_notification(
                session,
                user_id=complaint.user_id,
                kind=kind,
                title=title,
                body=body,
                link="/support",
            )
            has_inapp = True
        except Exception:
            logging.getLogger("doday.notifications").warning(
                "не создал уведомление автору обращения", exc_info=True
            )

    if complaint.contact_email and (email_when_inapp or not has_inapp):
        try:
            from app.auth.email import send_support_reply_to_user

            await send_support_reply_to_user(
                to=complaint.contact_email, subject=subject, title=title, body=body
            )
        except Exception:
            logging.getLogger("doday.notifications").warning(
                "не отправил письмо автору обращения", exc_info=True
            )


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
        contact_email=payload.contact_email or user.email,
        page_url=payload.page_url,
        viewport=payload.viewport,
        user_agent=payload.user_agent,
    )
    # Письмо владельцу — тем же путём, что и с публичной формы. Best-effort:
    # обращение уже сохранено и видно в /app/root, даже если SMTP молчит.
    try:
        from app.auth.email import send_support_notification
        from app.config import get_settings

        await send_support_notification(
            to=get_settings().root_admin_email,
            message=payload.body,
            reply_to=payload.contact_email or user.email,
            from_user=user.email,
            page_url=payload.page_url,
        )
    except Exception:
        import logging

        logging.getLogger("doday.support").warning(
            "не удалось отправить письмо о жалобе (сохранена на сайте)", exc_info=True
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
    before = await get_complaint(session, complaint_id)
    if before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")
    # Захватываем ДО обновления: after — тот же объект в identity map, его status
    # мутирует update_complaint, поэтому сравнивать после было бы поздно.
    was_in_progress = before.status == "in_progress"

    c = await update_complaint(
        session,
        complaint_id,
        status=payload.status,
        priority=payload.priority,
        admin_note=payload.admin_note,
    )
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")

    # Автору — уведомление, когда обращение ТОЛЬКО ЧТО взяли в работу.
    if payload.status == "in_progress" and not was_in_progress:
        await _notify_complaint_author(
            session,
            c,
            kind="support_in_progress",
            title="Твоё обращение взяли в работу 🛠️",
            body="Мы посмотрели твоё сообщение в поддержку и занялись им. Скоро ответим.",
            subject="Doday: твоё обращение взяли в работу",
            email_when_inapp=False,  # зарегистрированному хватит колокольчика
        )
    return ComplaintOut.model_validate(c)


class ComplaintReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@admin_router.post("/complaints/{complaint_id}/reply", response_model=ComplaintOut)
async def admin_reply_complaint(
    complaint_id: UUID,
    payload: ComplaintReplyIn,
    _: RequiredAdmin,
    session: DbSession,
) -> ComplaintOut:
    """Ответить автору обращения: сохраняем ответ и шлём его пользователю
    (колокольчик + письмо), чтобы он увидел ответ и в приложении, и на почте."""
    c = await get_complaint(session, complaint_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")
    reply = payload.body.strip()[:4000]
    c.admin_reply = reply
    await session.commit()
    await session.refresh(c)

    await _notify_complaint_author(
        session,
        c,
        kind="support_reply",
        title="Ответ поддержки Doday 💬",
        body=reply,
        subject="Ответ поддержки Doday",
        email_when_inapp=True,  # ответ важен — дублируем и в письмо
    )
    return ComplaintOut.model_validate(c)


@admin_router.delete("/complaints/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_complaint(
    complaint_id: UUID,
    _: RequiredAdmin,
    session: DbSession,
) -> None:
    if not await delete_complaint(session, complaint_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "complaint not found")


class PurgeUnverifiedOut(BaseModel):
    deleted: int


@admin_router.post("/users/purge-unverified", response_model=PurgeUnverifiedOut)
async def admin_purge_unverified(
    _: RequiredAdmin, session: DbSession, days: int = 3
) -> PurgeUnverifiedOut:
    """Удаляет НЕподтверждённые аккаунты старше N дней (вероятные боты).

    Подтверждённых и админов не трогает. days по умолчанию 3 — свежие
    регистрации, которые ещё могут подтвердиться, не сносим.
    """
    deleted = await purge_unverified(session, older_than_days=max(0, days))
    return PurgeUnverifiedOut(deleted=deleted)


@admin_router.get("/_userdiag", include_in_schema=False)
async def _userdiag(session: DbSession) -> dict[str, object]:
    """ВРЕМЕННО, без авторизации: агрегаты по юзерам, чтобы понять боты/живые.

    Полные емейлы наружу НЕ отдаём — только домены, маска (a***@gmail.com) и
    разброс регистраций по дням. Убрать после диагностики.
    """
    from collections import Counter

    from sqlalchemy import func, select

    from app.auth.models import User

    total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    verified = (
        await session.execute(
            select(func.count()).select_from(User).where(User.email_verified_at.is_not(None))
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(User.email, User.email_verified_at, User.created_at).order_by(User.created_at)
        )
    ).all()

    def _domain(e: str) -> str:
        return e.rsplit("@", 1)[-1].lower() if "@" in e else "(no@)"

    def _mask(e: str) -> str:
        name, _, dom = e.partition("@")
        return (name[:1] or "?") + "***@" + dom

    unv = [r for r in rows if r[1] is None]
    ver = [r for r in rows if r[1] is not None]
    real = {
        "gmail.com",
        "mail.ru",
        "yandex.ru",
        "ya.ru",
        "outlook.com",
        "icloud.com",
        "bk.ru",
        "inbox.ru",
        "list.ru",
        "rambler.ru",
    }
    unv_real = sum(1 for r in unv if _domain(r[0]) in real)
    return {
        "total": total,
        "verified": verified,
        "unverified": total - verified,
        "unverified_on_real_domains": unv_real,
        "unverified_on_other_domains": len(unv) - unv_real,
        "unverified_top_domains": dict(Counter(_domain(r[0]) for r in unv).most_common(15)),
        "verified_top_domains": dict(Counter(_domain(r[0]) for r in ver).most_common(10)),
        "unverified_samples_masked": [_mask(r[0]) for r in unv[:25]],
        "signups_by_day": dict(sorted(Counter(r[2].date().isoformat() for r in rows).items())),
    }


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
