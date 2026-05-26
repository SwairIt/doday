"""Lessio landing page — web-first продуктовый landing (заменил TG-валидацию-фазу).

Waitlist-endpoint остаётся живой backwards-compat (старые email юзеров не теряем),
но landing больше не показывает waitlist-форму — заменили на «Стать репетитором» CTA.
"""

from httpx import AsyncClient


async def test_lessio_landing_renders_with_real_product_messaging(
    client: AsyncClient,
) -> None:
    response = await client.get("/lessio")
    assert response.status_code == 200
    body = response.text
    assert "Lessio" in body
    assert "репетиторов" in body
    # Web-first headline (а не «прямо в Telegram»)
    assert "без переводов на сбер" in body.lower() or "без переводов" in body


async def test_lessio_landing_primary_cta_links_to_register(
    client: AsyncClient,
) -> None:
    response = await client.get("/lessio")
    body = response.text
    assert "/lessio/auth/register" in body
    assert "Стать репетитором" in body or "Создать страницу" in body


async def test_lessio_landing_has_features_section(
    client: AsyncClient,
) -> None:
    response = await client.get("/lessio")
    body = response.text
    # Ключевые фичи продукта упомянуты
    assert "Google Calendar" in body
    assert "напоминан" in body.lower()
    assert "Отзыв" in body or "отзыв" in body


async def test_lessio_landing_has_demo_profile_link(client: AsyncClient) -> None:
    response = await client.get("/lessio")
    assert "/u/demo" in response.text


async def test_lessio_landing_seo_meta(client: AsyncClient) -> None:
    response = await client.get("/lessio")
    body = response.text
    assert '<link rel="canonical" href="https://getdoday.ru/lessio"' in body
    assert 'property="og:title"' in body
    assert 'property="og:url"' in body


async def test_lessio_landing_trailing_slash_also_works(client: AsyncClient) -> None:
    response = await client.get("/lessio/")
    assert response.status_code == 200
    assert "Lessio" in response.text


# ── Waitlist API остаётся (admin pull + legacy) — back-compat ────────


async def test_waitlist_creates_entry(client: AsyncClient) -> None:
    response = await client.post(
        "/lessio/waitlist",
        data={
            "email": "tutor1@example.com",
            "niche": "english",
            "pain_point": "слишком много переписки",
            "telegram_handle": "@tutor1",
        },
    )
    assert response.status_code == 200


async def test_waitlist_idempotent_by_email(client: AsyncClient) -> None:
    payload_base = {"email": "tutor-idem@example.com", "niche": "english"}
    first = await client.post("/lessio/waitlist", data=payload_base)
    assert first.status_code == 200
    second = await client.post(
        "/lessio/waitlist",
        data={**payload_base, "pain_point": "uppdate"},
    )
    assert second.status_code == 200
