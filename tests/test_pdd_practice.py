"""Attempt persistence + the /pdd/my mistakes page."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.pdd.models import PddAttempt, PddQuestion
from app.pdd.seed_load import load_dataset, public_slug_for

_DATASET = [
    {
        "ticket": 1,
        "position": 1,
        "topic_slug": "znaki",
        "topic_title": "Знаки",
        "text": "Вопрос с верным вариантом 1?",
        "options": ["Верный", "Неверный"],
        "correct_position": 1,
        "explanation": "Пояснение.",
    },
]


@pytest.fixture
async def seeded_qid(db_session) -> int:
    await load_dataset(db_session, _DATASET)
    q = (
        await db_session.execute(
            select(PddQuestion).where(PddQuestion.public_slug == public_slug_for("ABM", 1, 1))
        )
    ).scalar_one()
    return q.id


async def test_anonymous_attempt_requires_login(client, seeded_qid):
    r = await client.post(
        "/api/pdd/attempt", json={"question_id": seeded_qid, "chosen_position": 1}
    )
    assert r.status_code == 401


async def test_correct_attempt_recorded(logged_in_client, seeded_qid, db_session):
    r = await logged_in_client.post(
        "/api/pdd/attempt",
        json={"question_id": seeded_qid, "chosen_position": 1, "source": "practice"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is True
    assert body["correct_position"] == 1
    assert body["explanation"] == "Пояснение."
    n = (await db_session.execute(select(func.count()).select_from(PddAttempt))).scalar_one()
    assert n == 1


async def test_wrong_attempt_shows_on_my_page(logged_in_client, seeded_qid):
    resp = await logged_in_client.post(
        "/api/pdd/attempt", json={"question_id": seeded_qid, "chosen_position": 2}
    )
    assert resp.json()["is_correct"] is False
    my = await logged_in_client.get("/pdd/my")
    assert my.status_code == 200
    assert "Вопрос с верным вариантом 1?" in my.text


async def test_latest_correct_clears_mistake(logged_in_client, seeded_qid):
    # wrong, then correct → latest attempt is correct → not a current mistake
    await logged_in_client.post(
        "/api/pdd/attempt", json={"question_id": seeded_qid, "chosen_position": 2}
    )
    await logged_in_client.post(
        "/api/pdd/attempt", json={"question_id": seeded_qid, "chosen_position": 1}
    )
    my = await logged_in_client.get("/pdd/my")
    assert "Вопросы, где ты ошибся" in my.text
    # the question should no longer be listed as a mistake card
    assert "Ошибок нет" in my.text


async def test_attempt_unknown_question_404(logged_in_client):
    r = await logged_in_client.post(
        "/api/pdd/attempt", json={"question_id": 999999, "chosen_position": 1}
    )
    assert r.status_code == 404


async def test_my_redirects_anonymous(client):
    r = await client.get("/pdd/my", follow_redirects=False)
    assert r.status_code == 303
    assert "/auth/login" in r.headers["location"]
