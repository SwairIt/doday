"""Tests for the standalone per-feature Entitlement mechanism (powers ПДД Pro).

The critical regression guard here is that existing tier products
(`pro_*` / `tutor_pro_*`) keep setting `user.tier` + `user.pro_until` and do NOT
create entitlements — the billing change must be byte-for-byte invisible to
Doday Tasks / Lessio.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.schemas import RegisterIn
from app.auth.service import register_user
from app.billing.models import Entitlement
from app.billing.products import get_product
from app.billing.service import has_entitlement
from app.billing.stars import apply_successful_payment, sign_payload


async def _mk_user(db_session, email: str = "pdd@example.com"):
    user = await register_user(db_session, RegisterIn(email=email, password="strongpass123"))
    await db_session.flush()
    return user


# ─── model ──────────────────────────────────────────────────────────────────


async def test_entitlement_unique_per_user_feature(db_session):
    user = await _mk_user(db_session, "uniq@example.com")
    db_session.add(
        Entitlement(user_id=user.id, feature="pdd_pro", source_code="pdd_pro_3m", expires_at=None)
    )
    await db_session.flush()
    db_session.add(
        Entitlement(user_id=user.id, feature="pdd_pro", source_code="pdd_pro_1m", expires_at=None)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ─── catalog ────────────────────────────────────────────────────────────────


def test_pdd_products_grant_entitlement_not_tier():
    p = get_product("pdd_pro_3m")
    assert p is not None
    assert p.grants_tier is None
    assert p.grants_entitlement == "pdd_pro"
    assert p.duration_months == 3
    assert p.stars_amount == 399


def test_existing_pro_product_unchanged():
    p = get_product("pro_1m")
    assert p is not None
    assert p.grants_tier == "pro"
    assert p.grants_entitlement is None


# ─── payment apply ──────────────────────────────────────────────────────────


async def test_pdd_payment_grants_entitlement_not_tier(db_session):
    user = await _mk_user(db_session, "grant@example.com")
    payload = sign_payload("pdd_pro_3m", user.id)
    await apply_successful_payment(
        db_session,
        telegram_payment_charge_id="ch_pdd_1",
        provider_payment_charge_id=None,
        payload=payload,
        stars_amount=399,
    )
    await db_session.refresh(user)
    # global tier untouched
    assert user.tier == "free"
    assert user.pro_until is None
    ent = (
        await db_session.execute(
            select(Entitlement).where(
                Entitlement.user_id == user.id, Entitlement.feature == "pdd_pro"
            )
        )
    ).scalar_one()
    assert ent.expires_at is not None and ent.expires_at > datetime.now(UTC)
    assert await has_entitlement(db_session, user, "pdd_pro") is True


async def test_pro_payment_still_sets_tier_and_no_entitlement(db_session):
    """Regression: tier products are unaffected by the entitlement branch."""
    user = await _mk_user(db_session, "tier@example.com")
    payload = sign_payload("pro_1m", user.id)
    await apply_successful_payment(
        db_session,
        telegram_payment_charge_id="ch_pro_1",
        provider_payment_charge_id=None,
        payload=payload,
        stars_amount=250,
    )
    # apply_successful_payment doesn't self-commit (the bot handler does); commit
    # here before refresh so we read the persisted row, not a discarded in-memory edit.
    await db_session.commit()
    await db_session.refresh(user)
    assert user.tier == "pro"
    assert user.pro_until is not None
    rows = (
        await db_session.execute(select(Entitlement).where(Entitlement.user_id == user.id))
    ).all()
    assert rows == []


async def test_renewal_extends_entitlement(db_session):
    user = await _mk_user(db_session, "renew@example.com")
    for charge in ("ch_r1", "ch_r2"):
        await apply_successful_payment(
            db_session,
            telegram_payment_charge_id=charge,
            provider_payment_charge_id=None,
            payload=sign_payload("pdd_pro_1m", user.id),
            stars_amount=199,
        )
    ent = (
        await db_session.execute(select(Entitlement).where(Entitlement.user_id == user.id))
    ).scalar_one()
    # two stacked 1-month grants ≈ 60 days out
    assert (ent.expires_at - datetime.now(UTC)).days >= 58


async def test_lifetime_entitlement(db_session):
    user = await _mk_user(db_session, "life@example.com")
    await apply_successful_payment(
        db_session,
        telegram_payment_charge_id="ch_life",
        provider_payment_charge_id=None,
        payload=sign_payload("pdd_pro_forever", user.id),
        stars_amount=990,
    )
    ent = (
        await db_session.execute(select(Entitlement).where(Entitlement.user_id == user.id))
    ).scalar_one()
    assert ent.expires_at is None  # lifetime
    assert await has_entitlement(db_session, user, "pdd_pro") is True


async def test_lifetime_not_downgraded_by_dated_purchase(db_session):
    user = await _mk_user(db_session, "lifekeep@example.com")
    await apply_successful_payment(
        db_session,
        telegram_payment_charge_id="ch_l1",
        provider_payment_charge_id=None,
        payload=sign_payload("pdd_pro_forever", user.id),
        stars_amount=990,
    )
    await apply_successful_payment(
        db_session,
        telegram_payment_charge_id="ch_l2",
        provider_payment_charge_id=None,
        payload=sign_payload("pdd_pro_1m", user.id),
        stars_amount=199,
    )
    ent = (
        await db_session.execute(select(Entitlement).where(Entitlement.user_id == user.id))
    ).scalar_one()
    assert ent.expires_at is None  # still lifetime


async def test_has_entitlement_false_without_grant(db_session):
    user = await _mk_user(db_session, "none@example.com")
    assert await has_entitlement(db_session, user, "pdd_pro") is False


async def test_tasks_catalog_excludes_pdd(logged_in_client):
    resp = await logged_in_client.get("/api/billing/products")
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert "pro_1m" in codes
    assert not any(c.startswith("pdd_") for c in codes)
