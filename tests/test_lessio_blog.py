"""Lessio blog routes + sitemap inclusion + JSON-LD."""

from __future__ import annotations

from httpx import AsyncClient

from app.lessio.blog.posts import POSTS, get_post, search_posts


async def test_blog_index_renders(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog")
    assert resp.status_code == 200
    body = resp.text
    # Все статьи имеют link на /lessio/blog/<slug>
    for p in POSTS:
        assert f"/lessio/blog/{p['slug']}" in body


async def test_blog_index_groups_by_category(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog")
    assert resp.status_code == 200
    body = resp.text
    assert "Сравнения" in body
    assert "Гайды" in body
    assert "Объяснения" in body


async def test_blog_post_renders_by_slug(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog/calendly-vs-lessio")
    assert resp.status_code == 200
    body = resp.text
    post = get_post("calendly-vs-lessio")
    assert post is not None
    assert post["title"] in body
    assert post["summary"] in body
    # Body — больше чем placeholder
    assert len(post["body"]) > 500


async def test_blog_bad_slug_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog/no-such-post")
    assert resp.status_code == 404


async def test_blog_search_finds_posts(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog?q=Calendly")
    assert resp.status_code == 200
    assert "calendly-vs-lessio" in resp.text


async def test_blog_search_empty_state(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog?q=ZZZNONEXIST")
    assert resp.status_code == 200
    body = resp.text
    assert "не нашл" in body.lower() or "ничего" in body.lower()


async def test_blog_post_has_blogposting_jsonld(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog/calendly-vs-lessio")
    assert resp.status_code == 200
    body = resp.text
    assert '"@type": "BlogPosting"' in body
    assert '"@type": "BreadcrumbList"' in body
    assert 'href="https://getdoday.ru/lessio/blog/calendly-vs-lessio"' in body


async def test_blog_index_has_blog_jsonld(client: AsyncClient) -> None:
    resp = await client.get("/lessio/blog")
    assert resp.status_code == 200
    body = resp.text
    assert '"@type": "Blog"' in body
    assert '"@type": "BreadcrumbList"' in body


async def test_sitemap_includes_blog_posts(client: AsyncClient) -> None:
    resp = await client.get("/sitemap.xml")
    assert resp.status_code == 200
    body = resp.text
    for p in POSTS:
        assert f"/lessio/blog/{p['slug']}" in body
    assert "/lessio/blog" in body


async def test_robots_allows_blog(client: AsyncClient) -> None:
    resp = await client.get("/robots.txt")
    assert resp.status_code == 200
    assert "Allow: /lessio/blog" in resp.text


async def test_search_function_unit() -> None:
    # «Telegram Stars» должен матчить chto-takoe-telegram-stars в top
    results = search_posts("Telegram Stars")
    assert results
    top_slugs = [p["slug"] for p in results[:3]]
    # один из топ-3 должен быть наш Stars-explainer или comparison
    assert any("telegram-stars" in s for s in top_slugs) or any("stars" in s for s in top_slugs)


async def test_all_posts_have_complete_content() -> None:
    """Sanity check — никаких placeholder'ов, у всех 18 статей есть body."""
    assert len(POSTS) == 18, f"expected 18 blog posts, got {len(POSTS)}"
    for p in POSTS:
        assert p["body"].strip(), f"empty body: {p['slug']}"
        assert len(p["body"]) > 1000, f"too short: {p['slug']}, len={len(p['body'])}"
        assert p["title"]
        assert p["summary"]
        assert p["hero_emoji"]
        assert p["reading_min"] > 0
        assert p["category"] in {"Сравнения", "Гайды", "Объяснения"}
