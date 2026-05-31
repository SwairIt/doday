"""Content-layer tests for Doday PDD: models + idempotent seed loader."""

from __future__ import annotations

from sqlalchemy import func, select

from app.pdd.models import PddOption, PddQuestion, PddTicket, PddTopic
from app.pdd.seed_load import load_dataset, public_slug_for

_DATASET = [
    {
        "ticket": 1,
        "position": 1,
        "topic_slug": "dorozhnye-znaki",
        "topic_title": "Дорожные знаки",
        "topic_position": 1,
        "text": "Что означает этот знак?",
        "image": "pdd/img/1_1.jpg",
        "options": ["Главная дорога", "Уступи дорогу", "Движение запрещено"],
        "correct_position": 1,
        "explanation": "Знак 2.1 «Главная дорога».",
    },
    {
        "ticket": 1,
        "position": 2,
        "topic_slug": "obgon",
        "topic_title": "Обгон, опережение",
        "topic_position": 2,
        "text": "Разрешён ли обгон?",
        "options": ["Разрешён", "Запрещён"],
        "correct_position": 2,
        "explanation": "Обгон запрещён на перекрёстке.",
    },
]


async def test_models_create(db_session):
    topic = PddTopic(slug="signs", title="Знаки", position=1, description="", seo_intro="")
    ticket = PddTicket(number=1)
    db_session.add_all([topic, ticket])
    await db_session.flush()
    q = PddQuestion(
        public_slug="bilet-1-vopros-1",
        ticket_id=ticket.id,
        position_in_ticket=1,
        topic_id=topic.id,
        text="?",
        explanation="...",
        correct_position=1,
    )
    db_session.add(q)
    await db_session.flush()
    db_session.add(PddOption(question_id=q.id, position=1, text="A"))
    await db_session.flush()


async def test_seed_loads_and_is_idempotent(db_session):
    counts = await load_dataset(db_session, _DATASET)
    assert counts == {"topics": 2, "tickets": 1, "questions": 2, "options": 5}

    # second run: nothing new created, options rebuilt, no duplicates
    counts2 = await load_dataset(db_session, _DATASET)
    assert counts2["topics"] == 0
    assert counts2["tickets"] == 0
    assert counts2["questions"] == 0

    n_topics = (await db_session.execute(select(func.count()).select_from(PddTopic))).scalar_one()
    n_q = (await db_session.execute(select(func.count()).select_from(PddQuestion))).scalar_one()
    n_opt = (await db_session.execute(select(func.count()).select_from(PddOption))).scalar_one()
    assert n_topics == 2
    assert n_q == 2
    assert n_opt == 5  # 3 + 2

    q1 = (
        await db_session.execute(
            select(PddQuestion).where(PddQuestion.public_slug == public_slug_for(1, 1))
        )
    ).scalar_one()
    assert q1.correct_position == 1
    assert q1.image_path == "pdd/img/1_1.jpg"
