"""Billing HTTP endpoints — read current tier + change for testing."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth.deps import DbSession, RequiredUser
from app.billing.service import (
    TIERS,
    effective_tier,
    is_trial_active,
    limits_for,
    trial_days_remaining,
)


class TierMeOut(BaseModel):
    user_id: UUID
    tier: str
    effective_tier: str
    trial_active: bool
    trial_ends_at: datetime | None
    trial_days_remaining: int
    limits: dict[str, object]


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
        limits=dict(limits_for(user)),
    )


@router.get("/tiers")
async def list_tiers(_: RequiredUser) -> dict[str, dict[str, object]]:
    """Public catalog of tier limits — used by the pricing section on landing."""
    return {tier: dict(lim) for tier, lim in TIERS.items()}


@router.post("/change-tier", response_model=TierMeOut)
async def change_tier(
    payload: ChangeTierPayload, user: RequiredUser, session: DbSession
) -> TierMeOut:
    """Self-service tier change. Real billing would gate this behind a payment."""
    if payload.tier not in TIERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "неизвестный тариф")
    user.tier = payload.tier
    await session.commit()
    await session.refresh(user)
    return TierMeOut(
        user_id=user.id,
        tier=user.tier,
        effective_tier=effective_tier(user),
        trial_active=is_trial_active(user),
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=trial_days_remaining(user),
        limits=dict(limits_for(user)),
    )
