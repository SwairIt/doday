"""Exam simulator: pure scoring + the Pro-gated save endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.billing.models import Entitlement
from app.pdd.models import PddExamSession, PddQuestion
from app.pdd.seed_load import load_dataset
from app.pdd.service import score_exam

# ─── pure scoring (no DB) ───────────────────────────────────────────────────


def test_score_all_correct_passes():
    correct = {1: 1, 2: 2, 3: 1}
    passed, mistakes, extra = score_exam({1: 1, 2: 2, 3: 1}, correct)
    assert passed is True
    assert mistakes == 0
    assert extra == 0


def test_score_two_mistakes_still_passes():
    correct = {1: 1, 2: 1, 3: 1, 4: 1}
    passed, mistakes, extra = score_exam({1: 2, 2: 2, 3: 1, 4: 1}, correct)
    assert mistakes == 2
    assert passed is True
    assert extra == 10


def test_score_three_mistakes_fails():
    correct = {1: 1, 2: 1, 3: 1, 4: 1}
    passed, mistakes, _ = score_exam({1: 2, 2: 2, 3: 2, 4: 1}, correct)
    assert mistakes == 3
    assert passed is False


def test_unanswered_counts_as_mistake():
    correct = {1: 1, 2: 1}
    _, mistakes, _ = score_exam({1: 1}, correct)  # q2 unanswered
    assert mistakes == 1


# ─── save endpoint gating + persistence (DB) ────────────────────────────────

_ONEQ = [
    {
        "ticket": 1,
        "position": 1,
        "topic_slug": "t",
        "topic_title": "Тема",
        "text": "Вопрос?",
        "options": ["A", "B"],
        "correct_position": 1,
        "explanation": "",
    }
]


async def _grant_pdd_pro(db_session, email: str = "logged-in@example.com") -> User:
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
    return user


@pytest.fixture
async def qid(db_session) -> int:
    await load_dataset(db_session, _ONEQ)
    return (await db_session.execute(select(PddQuestion.id))).scalar_one()


async def test_exam_save_402_without_pro(logged_in_client, qid):
    r = await logged_in_client.post(
        "/api/pdd/exam/save", json={"answers": [{"question_id": qid, "chosen_position": 1}]}
    )
    assert r.status_code == 402


async def test_exam_save_persists_for_pro(logged_in_client, db_session, qid):
    await _grant_pdd_pro(db_session)
    r = await logged_in_client.post(
        "/api/pdd/exam/save", json={"answers": [{"question_id": qid, "chosen_position": 1}]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["total"] == 1
    n = (await db_session.execute(select(func.count()).select_from(PddExamSession))).scalar_one()
    assert n == 1
