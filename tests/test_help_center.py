"""Tests for the help center pages."""

from httpx import AsyncClient

from app.help.articles import ARTICLES


async def test_help_index_lists_all_articles(client: AsyncClient) -> None:
    response = await client.get("/help")
    assert response.status_code == 200
    body = response.text
    assert "Как пользоваться Doday" in body
    for article in ARTICLES:
        assert article["title"] in body
        assert f"/help/{article['slug']}" in body


async def test_help_article_renders(client: AsyncClient) -> None:
    response = await client.get("/help/quick-start")
    assert response.status_code == 200
    body = response.text
    assert "С чего начать" in body
    # Sidebar with all articles must be visible.
    for article in ARTICLES:
        assert article["title"] in body


async def test_help_article_has_prev_next_nav(client: AsyncClient) -> None:
    # First article — no Prev, has Next.
    body = (await client.get(f"/help/{ARTICLES[0]['slug']}")).text
    assert ARTICLES[1]["title"] in body  # Next link

    # Last article — has Prev, no Next.
    body = (await client.get(f"/help/{ARTICLES[-1]['slug']}")).text
    assert ARTICLES[-2]["title"] in body  # Prev link


async def test_help_unknown_article_404(client: AsyncClient) -> None:
    response = await client.get("/help/no-such-article-anywhere")
    assert response.status_code == 404


async def test_help_link_appears_on_landing(client: AsyncClient) -> None:
    """Doday Tasks landing at /doday links to /help."""
    body = (await client.get("/doday")).text
    assert "/help" in body
