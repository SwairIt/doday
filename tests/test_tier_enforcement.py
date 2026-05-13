"""Verify Pro-features are gated correctly per TIERS.

Each TIERS feature flag must enforce in 2 places:
1. UI / endpoint — Free user gets 402 Payment Required when trying to opt-in
2. Service-layer — even if endpoint bypassed, downstream still respects tier

Tests cover: email_digest, tg_bot, trash retention, premium_themes (UI-only),
and the new helper `require_pro` raising 402.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.service import register_user
from app.billing.service import (
    effective_tier,
    has_pro_features,
    require_pro,
)


async def _make_user(
    db_session: AsyncSession,
    email: str,
    tier: str = "free",
    trial_active: bool = False,
) -> User:
    user = await register_user(db_session, RegisterIn(email=email, password="strongpass123"))
    user.email_verified_at = datetime.now(UTC)
    user.tier = tier
    if trial_active:
        user.trial_ends_at = datetime.now(UTC) + timedelta(days=10)
    else:
        user.trial_ends_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# --- helper-level tests -----------------------------------------------------


async def test_has_pro_features_free_no_trial(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "free-no-trial@test.com", tier="free", trial_active=False)
    assert has_pro_features(user) is False
    assert effective_tier(user) == "free"


async def test_has_pro_features_free_with_trial(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "trial@test.com", tier="free", trial_active=True)
    assert has_pro_features(user) is True
    assert effective_tier(user) == "pro"


async def test_has_pro_features_pro(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "pro@test.com", tier="pro", trial_active=False)
    assert has_pro_features(user) is True


async def test_beta_free_for_all_promotes_free_to_pro(db_session: AsyncSession) -> None:
    """Habr-launch flag: BETA_FREE_FOR_ALL=true → все юзеры получают Pro."""
    from app.config import get_settings

    user = await _make_user(db_session, "beta@test.com", tier="free", trial_active=False)
    assert has_pro_features(user) is False  # baseline (autouse fixture disables flag)

    s = get_settings()
    s.beta_free_for_all = True
    try:
        assert effective_tier(user) == "pro"
        assert has_pro_features(user) is True
    finally:
        s.beta_free_for_all = False


async def test_require_pro_raises_402_for_free(db_session: AsyncSession) -> None:
    from fastapi import HTTPException

    user = await _make_user(db_session, "f@test.com", tier="free", trial_active=False)
    with pytest.raises(HTTPException) as exc:
        require_pro(user, "test")
    assert exc.value.status_code == 402


async def test_require_pro_passes_for_pro(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "p@test.com", tier="pro", trial_active=False)
    require_pro(user, "test")  # no exception


async def test_require_pro_passes_for_free_with_trial(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "trial@test.com", tier="free", trial_active=True)
    require_pro(user, "test")  # no exception (trial gives Pro features)


# --- email_digest endpoint gating ------------------------------------------


async def test_morning_digest_blocks_free(db_session: AsyncSession, client: AsyncClient) -> None:
    """Free user без trial → 402 при попытке включить дайджест."""
    _ = await _make_user(db_session, "fd@test.com", tier="free", trial_active=False)
    login = await client.post(
        "/auth/login",
        data={"email": "fd@test.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.post("/api/profile/morning-digest", data={"enabled": "true"})
    assert r.status_code == 402


async def test_morning_digest_allows_pro(db_session: AsyncSession, client: AsyncClient) -> None:
    _ = await _make_user(db_session, "pd@test.com", tier="pro", trial_active=False)
    login = await client.post(
        "/auth/login",
        data={"email": "pd@test.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.post("/api/profile/morning-digest", data={"enabled": "true"})
    assert r.status_code == 200
    assert r.json()["enabled"] is True


async def test_morning_digest_allows_disable_for_free(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Free может ВЫКЛЮЧИТЬ (например, после окончания trial хочет отписаться)."""
    user = await _make_user(db_session, "fdd@test.com", tier="free", trial_active=False)
    user.morning_digest_enabled = True  # как будто включил во время trial
    await db_session.commit()
    login = await client.post(
        "/auth/login",
        data={"email": "fdd@test.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.post("/api/profile/morning-digest", data={"enabled": "false"})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


# --- tg_bot endpoint gating -------------------------------------------------


async def test_telegram_link_blocks_free(db_session: AsyncSession, client: AsyncClient) -> None:
    _ = await _make_user(db_session, "ftg@test.com", tier="free", trial_active=False)
    login = await client.post(
        "/auth/login",
        data={"email": "ftg@test.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.post("/api/profile/telegram-link")
    assert r.status_code == 402


async def test_telegram_link_allows_pro(db_session: AsyncSession, client: AsyncClient) -> None:
    _ = await _make_user(db_session, "ptg@test.com", tier="pro", trial_active=False)
    login = await client.post(
        "/auth/login",
        data={"email": "ptg@test.com", "password": "strongpass123"},
    )
    assert login.status_code == 303
    r = await client.post("/api/profile/telegram-link")
    assert r.status_code == 200
    assert "deeplink" in r.json()


# --- trash retention by tier -----------------------------------------------


async def test_trash_retention_free_is_14_days(
    db_session: AsyncSession,
) -> None:
    from app.billing.service import limits_for

    user = await _make_user(db_session, "ftr@test.com", tier="free", trial_active=False)
    assert limits_for(user)["trash_retention_days"] == 14


async def test_trash_retention_pro_is_30_days(
    db_session: AsyncSession,
) -> None:
    from app.billing.service import limits_for

    user = await _make_user(db_session, "ptr@test.com", tier="pro", trial_active=False)
    assert limits_for(user)["trash_retention_days"] == 30


# --- digest service skips free users ---------------------------------------


async def test_digest_send_all_skips_free(db_session: AsyncSession) -> None:
    """Free user with stale opt-in flag (trial expired) → не получает дайджест."""
    from unittest.mock import AsyncMock, patch

    from app.digest.service import send_morning_digests_for_all_users

    user = await _make_user(db_session, "fds@test.com", tier="free", trial_active=False)
    user.morning_digest_enabled = True  # stale opt-in
    await db_session.commit()

    with patch("app.digest.service.aiosmtplib.send", new=AsyncMock()) as mock_send:
        result = await send_morning_digests_for_all_users(db_session)

    assert result["skipped_free"] >= 1
    assert result["sent"] == 0
    mock_send.assert_not_called()
