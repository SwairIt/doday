"""Lessio help-center routes + search + sitemap inclusion."""

from __future__ import annotations

from httpx import AsyncClient

from app.lessio.help.articles import ARTICLES, get_article, search_articles


async def test_help_index_lists_all_articles(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help")
    assert resp.status_code == 200
    body = resp.text
    # Все 20+ статей должны иметь slug в HTML (как минимум линк-href)
    for art in ARTICLES:
        assert f"/lessio/help/{art['slug']}" in body


async def test_help_index_groups_by_category(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help")
    assert resp.status_code == 200
    body = resp.text
    # На index'е видны заголовки категорий
    assert "Начало" in body and "Профиль" in body and "Услуги" in body
    assert "Расписание" in body and "Оплата" in body


async def test_help_article_renders_by_slug(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help/quick-start")
    assert resp.status_code == 200
    body = resp.text
    art = get_article("quick-start")
    assert art is not None
    assert art["title"] in body
    assert art["summary"] in body


async def test_help_bad_slug_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help/no-such-article")
    assert resp.status_code == 404


async def test_help_search_finds_articles(client: AsyncClient) -> None:
    # Слово «оплата» должно матчить хотя бы payments-stars + payment-manual
    resp = await client.get("/lessio/help?q=оплата")
    assert resp.status_code == 200
    body = resp.text
    assert "payments-stars" in body or "payment-manual" in body


async def test_help_search_returns_empty_state_on_no_match(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help?q=ZZZZNONEXISTENT")
    assert resp.status_code == 200
    body = resp.text
    # Должна быть подсказка про пустой результат
    assert "не нашл" in body.lower() or "ничего" in body.lower() or "пуст" in body.lower()


async def test_help_articles_json_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help/articles.json")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) == len(ARTICLES)
    assert all("slug" in item and "title" in item for item in payload)


async def test_search_function_unit_scoring() -> None:
    # title match >> body match
    results = search_articles("публичная страница")
    assert results
    # public-profile должна быть первой — у неё title-match
    assert results[0]["slug"] == "public-profile"


async def test_sitemap_includes_lessio_help_articles(client: AsyncClient) -> None:
    resp = await client.get("/sitemap.xml")
    assert resp.status_code == 200
    body = resp.text
    for art in ARTICLES:
        assert f"/lessio/help/{art['slug']}" in body
    # И сам index
    assert "/lessio/help" in body


async def test_sitemap_includes_lessio_seo_landings(client: AsyncClient) -> None:
    """Niche-landings будут добавлены в N4 — пока проверяем что они уже в sitemap (URL'ы)."""
    resp = await client.get("/sitemap.xml")
    assert resp.status_code == 200
    body = resp.text
    for path in (
        "/lessio/dlya-repetitorov",
        "/lessio/dlya-trenerov",
        "/lessio/dlya-psihologov",
        "/lessio/alternativa-calendly",
        "/lessio/oplata-cherez-telegram",
    ):
        assert path in body


async def test_seo_niche_landings_render(client: AsyncClient) -> None:
    """Все 5 SEO-страниц должны рендериться 200 с canonical + JSON-LD."""
    for path, h1_marker in [
        ("/lessio/dlya-repetitorov", "Для репетиторов"),
        ("/lessio/dlya-trenerov", "Для онлайн-тренеров"),
        ("/lessio/dlya-psihologov", "Для психологов"),
        ("/lessio/alternativa-calendly", "Calendly"),
        ("/lessio/oplata-cherez-telegram", "Telegram"),
    ]:
        resp = await client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        body = resp.text
        # canonical
        assert f'href="https://getdoday.ru{path}"' in body, f"{path}: missing canonical"
        # JSON-LD schema.org
        assert "application/ld+json" in body, f"{path}: missing JSON-LD"
        assert "schema.org" in body, f"{path}: missing schema.org reference"
        # FAQPage Q&A
        assert "FAQPage" in body or "Service" in body or "HowTo" in body, (
            f"{path}: no structured-data type"
        )
        assert h1_marker.lower() in body.lower(), f"{path}: missing keyword '{h1_marker}'"


async def test_help_article_has_json_ld(client: AsyncClient) -> None:
    """Каждая help-статья должна содержать JSON-LD Article + BreadcrumbList."""
    resp = await client.get("/lessio/help/quick-start")
    assert resp.status_code == 200
    body = resp.text
    assert '"@type": "Article"' in body
    assert '"@type": "BreadcrumbList"' in body
    assert 'href="https://getdoday.ru/lessio/help/quick-start"' in body  # canonical


async def test_help_index_has_collection_page_jsonld(client: AsyncClient) -> None:
    resp = await client.get("/lessio/help")
    assert resp.status_code == 200
    body = resp.text
    assert '"@type": "CollectionPage"' in body
    assert '"@type": "BreadcrumbList"' in body


async def test_lessio_landing_has_software_app_jsonld(client: AsyncClient) -> None:
    resp = await client.get("/lessio")
    assert resp.status_code == 200
    body = resp.text
    assert '"@type": "SoftwareApplication"' in body
    assert '"@type": "Organization"' in body
    # Crosslinks на нишевые лендинги + help
    assert "/lessio/dlya-repetitorov" in body
    assert "/lessio/dlya-trenerov" in body
    assert "/lessio/dlya-psihologov" in body
    assert "/lessio/oplata-cherez-telegram" in body
    assert "/lessio/help" in body


async def test_robots_txt_allows_seo_pages(client: AsyncClient) -> None:
    resp = await client.get("/robots.txt")
    assert resp.status_code == 200
    body = resp.text
    # Cabinet/auth — закрыто
    assert "Disallow: /lessio/app/" in body
    assert "Disallow: /lessio/auth/" in body
    # SEO-страницы — открыты
    assert "Allow: /lessio/help" in body
    assert "Allow: /lessio/dlya-repetitorov" in body
    assert "Allow: /lessio/oplata-cherez-telegram" in body
    # Sitemap
    assert "Sitemap:" in body
