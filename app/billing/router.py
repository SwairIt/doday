"""Billing HTTP endpoints — read current tier, change tier (downgrade-only),
Telegram Stars invoice creation, and per-user payment history."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select

from app.auth.deps import DbSession, RequiredUser
from app.billing.models import StarPayment
from app.billing.products import PRODUCTS, get_product
from app.billing.service import (
    TIERS,
    effective_tier,
    is_trial_active,
    limits_for,
    trial_days_remaining,
)
from app.billing.stars import StarsError, create_invoice_link


class TierMeOut(BaseModel):
    user_id: UUID
    tier: str
    effective_tier: str
    trial_active: bool
    trial_ends_at: datetime | None
    trial_days_remaining: int
    pro_until: datetime | None
    limits: dict[str, object]


class ProductOut(BaseModel):
    code: str
    title: str
    description: str
    grants_tier: str
    duration_months: int | None
    stars_amount: int


class InvoiceCreateIn(BaseModel):
    product_code: str


class InvoiceCreateOut(BaseModel):
    invoice_url: str
    stars_amount: int
    product_code: str
    product_title: str


class PaymentHistoryItem(BaseModel):
    id: UUID
    product_code: str
    stars_amount: int
    status: str
    created_at: datetime
    refunded_at: datetime | None


class ChangeTierPayload(BaseModel):
    tier: Literal["free", "pro", "team"]


router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/me", response_model=TierMeOut)
async def me_endpoint(user: RequiredUser) -> TierMeOut:
    return TierMeOut(
        user_id=user.id,
        tier=user.tier,
        effective_tier=effective_tier(user),
        trial_active=is_trial_active(user),
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=trial_days_remaining(user),
        pro_until=user.pro_until,
        limits=dict(limits_for(user)),
    )


@router.get("/products", response_model=list[ProductOut])
async def list_products_endpoint(_: RequiredUser) -> list[ProductOut]:
    """Public catalog of buyable products — Mini App / pricing page consume this.

    During beta (`BETA_FREE_FOR_ALL=true`), the API returns ONLY the lifetime
    founder offer. Monthly / annual subs are confusing when everything is
    already free — anyone considering payment in beta is buying the
    «lock-in before paid mode returns» founder deal.
    """
    from app.config import get_settings

    beta = get_settings().beta_free_for_all
    products_visible = [p for p in PRODUCTS if p.code == "pro_forever"] if beta else list(PRODUCTS)
    return [
        ProductOut(
            code=p.code,
            title=p.title,
            description=p.description,
            grants_tier=p.grants_tier,
            duration_months=p.duration_months,
            stars_amount=p.stars_amount,
        )
        for p in products_visible
    ]


@router.post("/stars/invoice", response_model=InvoiceCreateOut)
async def create_stars_invoice(payload: InvoiceCreateIn, user: RequiredUser) -> InvoiceCreateOut:
    """Build a Telegram-hosted invoice link for the user x product.

    Frontend opens this URL via `Telegram.WebApp.openInvoice(url, callback)`
    inside Mini App, or via plain `window.location` in a browser (Telegram
    routes the user through the t.me deeplink).
    """
    product = get_product(payload.product_code)
    if product is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"продукт «{payload.product_code}» не найден"
        )
    try:
        invoice_url = await create_invoice_link(user, payload.product_code)
    except StarsError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return InvoiceCreateOut(
        invoice_url=invoice_url,
        stars_amount=product.stars_amount,
        product_code=product.code,
        product_title=product.title,
    )


@router.get("/stars/payments", response_model=list[PaymentHistoryItem])
async def list_my_payments(user: RequiredUser, session: DbSession) -> list[PaymentHistoryItem]:
    """Logged-in user sees their own payments — receipts, refund status."""
    rows = await session.execute(
        select(StarPayment)
        .where(StarPayment.user_id == user.id)
        .order_by(desc(StarPayment.created_at))
        .limit(50)
    )
    return [
        PaymentHistoryItem(
            id=p.id,
            product_code=p.product_code,
            stars_amount=p.stars_amount,
            status=p.status,
            created_at=p.created_at,
            refunded_at=p.refunded_at,
        )
        for p in rows.scalars().all()
    ]


@router.get("/tiers")
async def list_tiers(_: RequiredUser) -> dict[str, dict[str, object]]:
    """Public catalog of tier limits — used by the pricing section on landing."""
    return {tier: dict(lim) for tier, lim in TIERS.items()}


@router.post("/change-tier", response_model=TierMeOut)
async def change_tier(
    payload: ChangeTierPayload, user: RequiredUser, session: DbSession
) -> TierMeOut:
    """Self-service tier change. SAFE direction only — anyone can DOWNGRADE
    themselves to free; upgrades require payment (Stars or future ЮKassa).

    Closes the security gap from 2026-05-22 audit: previously this endpoint
    let any logged-in user POST `{"tier": "pro"}` and silently become Pro
    without paying. Now upgrades go through app/billing/stars.py only.
    """
    if payload.tier not in TIERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "неизвестный тариф")
    if payload.tier != "free":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Самовольное повышение тарифа запрещено. Оплати через Telegram Stars: "
            "POST /api/billing/stars/invoice",
        )
    user.tier = "free"
    user.pro_until = None  # explicit cancel — they want off.
    await session.commit()
    await session.refresh(user)
    return TierMeOut(
        user_id=user.id,
        tier=user.tier,
        effective_tier=effective_tier(user),
        trial_active=is_trial_active(user),
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=trial_days_remaining(user),
        pro_until=user.pro_until,
        limits=dict(limits_for(user)),
    )
