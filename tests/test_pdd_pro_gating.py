"""Pro-gating on /pdd/trener and /pdd/sbornik (entitlement-based, not global tier)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.models import User
from app.billing.models import Entitlement


async def _grant_pdd_pro(db_session, email: str = "logged-in@example.com") -> None:
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    db_session.add(
        Entitlement(
            user_id=user.id,
            feature="pdd_pro",
            source_code="test",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    await db_session.commit()


async def test_trainer_redirects_anonymous(client):
    r = await client.get("/pdd/trener", follow_redirects=False)
    assert r.status_code == 303
    assert "/auth/login" in r.headers["location"]


async def test_trainer_redirects_non_pro_to_pro_page(logged_in_client):
    r = await logged_in_client.get("/pdd/trener", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/pdd/pro"


async def test_trainer_ok_for_pro(logged_in_client, db_session):
    await _grant_pdd_pro(db_session)
    r = await logged_in_client.get("/pdd/trener")
    assert r.status_code == 200
    assert "Тренажёр ошибок" in r.text


async def test_sbornik_gated_then_ok(logged_in_client, db_session):
    blocked = await logged_in_client.get("/pdd/sbornik", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"] == "/pdd/pro"

    await _grant_pdd_pro(db_session)
    ok = await logged_in_client.get("/pdd/sbornik")
    assert ok.status_code == 200
    assert "Сборник к экзамену" in ok.text


async def test_global_pro_tier_does_not_unlock_pdd(logged_in_client, db_session):
    """A user with the global Doday Pro tier but no pdd_pro entitlement is still
    gated out of ПДД Pro — the standalone-entitlement guarantee."""
    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    user.tier = "pro"
    user.pro_until = datetime.now(UTC) + timedelta(days=30)
    await db_session.commit()
    r = await logged_in_client.get("/pdd/trener", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/pdd/pro"
