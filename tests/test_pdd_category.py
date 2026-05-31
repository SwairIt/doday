"""Category (ABM / CD) routing + the convenience features (search, deck,
random-ticket, ticket-progress)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.pdd import service
from app.pdd.models import PddQuestion
from app.pdd.seed_load import load_dataset

_ABM = [
    {
        "category": "ABM",
        "ticket": 1,
        "position": p,
        "topic_slug": "znaki",
        "topic_title": "Знаки",
        "text": f"Разрешён ли обгон в ситуации {p}?",
        "options": ["Да", "Нет"],
        "correct_position": 1,
        "explanation": "",
    }
    for p in (1, 2, 3)
]
_CD = [
    {
        "category": "CD",
        "ticket": 1,
        "position": 1,
        "topic_slug": "znaki",
        "topic_title": "Знаки",
        "text": "Вопрос про грузовик и прицеп",
        "options": ["Да", "Нет"],
        "correct_position": 2,
        "explanation": "",
    }
]


@pytest.fixture
async def seeded(db_session):
    await load_dataset(db_session, _ABM + _CD)


async def test_hubs_are_category_specific(client, seeded):
    abm = await client.get("/pdd/")
    cd = await client.get("/pdd/cd/")
    assert abm.status_code == 200 and cd.status_code == 200
    assert "Категории A, B, M" in abm.text
    assert "Категории C, D" in cd.text
    assert "/pdd/cd/" in abm.text  # selector links to CD


async def test_ticket_pages_separate_by_category(client, seeded):
    abm = await client.get("/pdd/bilet/1")
    cd = await client.get("/pdd/cd/bilet/1")
    assert "Разрешён ли обгон в ситуации 1?" in abm.text
    assert "грузовик" not in abm.text
    assert "Вопрос про грузовик и прицеп" in cd.text
    assert "getdoday.ru/pdd/cd/bilet/1" in cd.text  # category-aware canonical


async def test_search_scoped_to_category(client, seeded):
    abm = await client.get("/pdd/poisk", params={"q": "обгон"})
    assert "Разрешён ли обгон" in abm.text
    cd = await client.get("/pdd/cd/poisk", params={"q": "обгон"})
    assert "Разрешён ли обгон" not in cd.text  # ABM-only term, CD search empty


async def test_deck_returns_category_questions(client, seeded):
    r = await client.get("/api/pdd/deck", params={"category": "CD", "offset": 0, "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["questions"]) == 1
    assert "грузовик" in body["questions"][0]["text"]


async def test_random_ticket_redirects(client, seeded):
    r = await client.get("/pdd/cd/sluchainyi-bilet", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/pdd/cd/bilet/1"


async def test_ticket_progress_marks_started(db_session, seeded):
    from app.pdd.schemas import AttemptIn

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one_or_none()
    if user is None:
        from app.auth.schemas import RegisterIn
        from app.auth.service import register_user

        user = await register_user(
            db_session, RegisterIn(email="prog@example.com", password="strongpass123")
        )
        await db_session.flush()
    q = (
        await db_session.execute(
            select(PddQuestion).where(PddQuestion.public_slug == "bilet-1-vopros-1")
        )
    ).scalar_one()
    await service.record_attempt(db_session, user, AttemptIn(question_id=q.id, chosen_position=2))
    progress = await service.ticket_progress(db_session, user, "ABM")
    assert progress.get(1) == "started"  # answered one of the 20, not all-correct
