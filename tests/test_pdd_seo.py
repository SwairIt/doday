"""Public SEO pages for Doday PDD: hub, ticket, topic, question, sitemap, robots."""

from __future__ import annotations

import pytest

from app.pdd.seed_load import load_dataset, public_slug_for

_DATASET = [
    {
        "ticket": 1,
        "position": 1,
        "topic_slug": "dorozhnye-znaki",
        "topic_title": "Дорожные знаки",
        "topic_position": 1,
        "text": "Что означает этот знак ограничения?",
        "options": ["Главная дорога", "Уступи дорогу"],
        "correct_position": 1,
        "explanation": "Это знак приоритета.",
    },
    {
        "ticket": 1,
        "position": 2,
        "topic_slug": "obgon",
        "topic_title": "Обгон и опережение",
        "topic_position": 2,
        "text": "Разрешён ли обгон в этой ситуации?",
        "options": ["Разрешён", "Запрещён"],
        "correct_position": 2,
        "explanation": "Обгон здесь запрещён.",
    },
]


@pytest.fixture
async def seeded(db_session):
    await load_dataset(db_session, _DATASET)
    return _DATASET


async def test_hub_indexable(client, seeded):
    r = await client.get("/pdd/")
    assert r.status_code == 200
    assert "Билеты ПДД" in r.text


async def test_ticket_page_has_question_and_canonical(client, seeded):
    r = await client.get("/pdd/bilet/1")
    assert r.status_code == 200
    assert "Что означает этот знак ограничения?" in r.text
    assert 'rel="canonical"' in r.text
    assert "getdoday.ru/pdd/bilet/1" in r.text


async def test_unknown_ticket_404(client, seeded):
    r = await client.get("/pdd/bilet/999")
    assert r.status_code == 404


async def test_topic_page(client, seeded):
    r = await client.get("/pdd/tema/obgon")
    assert r.status_code == 200
    assert "Разрешён ли обгон в этой ситуации?" in r.text


async def test_question_page_has_jsonld(client, seeded):
    slug = public_slug_for(1, 1)
    r = await client.get(f"/pdd/vopros/{slug}")
    assert r.status_code == 200
    assert "application/ld+json" in r.text
    assert '"@type": "Question"' in r.text


async def test_sitemap_lists_questions(client, seeded):
    r = await client.get("/pdd/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert f"/pdd/vopros/{public_slug_for(1, 1)}" in r.text
    assert "/pdd/bilet/1" in r.text


async def test_pro_landing_shows_price(client, seeded):
    r = await client.get("/pdd/pro")
    assert r.status_code == 200
    assert "399" in r.text  # pdd_pro_3m hero price


async def test_robots_lists_pdd_sitemap(client):
    r = await client.get("/robots.txt")
    assert r.status_code == 200
    assert "/pdd/sitemap.xml" in r.text
    assert "Disallow: /pdd/trener" in r.text
