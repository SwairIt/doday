"""Lessio custom 404 page — branded для /lessio/* + /u/*."""

from __future__ import annotations

from httpx import AsyncClient


async def test_lessio_path_404_renders_branded_template(client: AsyncClient) -> None:
    """Несуществующий /lessio/* path даёт Lessio-брендированный 404."""
    resp = await client.get(
        "/lessio/no-such-page-here-12345",
        headers={"accept": "text/html"},
    )
    assert resp.status_code == 404
    body = resp.text
    # Brand
    assert "Lessio" in body
    # Branded copy
    assert "Не нашли страницу" in body or "404" in body
    # Cross-links к популярным
    assert "/lessio/help" in body
    assert "/lessio/blog" in body


async def test_lessio_help_unknown_slug_branded_404(client: AsyncClient) -> None:
    resp = await client.get(
        "/lessio/help/no-such-article-zzz",
        headers={"accept": "text/html"},
    )
    assert resp.status_code == 404
    body = resp.text
    # Должен быть Lessio-брендированный — search-input на blog
    assert "Lessio" in body
    assert "blog" in body  # на форму поиска


async def test_lessio_blog_unknown_slug_branded_404(client: AsyncClient) -> None:
    resp = await client.get(
        "/lessio/blog/no-such-post-xyz",
        headers={"accept": "text/html"},
    )
    assert resp.status_code == 404
    assert "Lessio" in resp.text


async def test_u_unknown_tutor_branded_404(client: AsyncClient) -> None:
    """Неизвестный tutor /u/<slug> тоже должен дать Lessio-404 (не Doday)."""
    resp = await client.get(
        "/u/nosuchtutor-zzzz",
        headers={"accept": "text/html"},
    )
    assert resp.status_code == 404
    body = resp.text
    # Lessio-брендированный шаблон
    assert "/lessio/help" in body or "/lessio/blog" in body


async def test_doday_404_remains_unbranded_for_lessio(client: AsyncClient) -> None:
    """Doday-paths должны продолжать использовать Doday-404."""
    resp = await client.get(
        "/no-such-doday-page-zzz-12345",
        headers={"accept": "text/html"},
    )
    assert resp.status_code == 404
    body = resp.text
    # Doday-404 имеет «улетела в космос» в копии
    assert "космос" in body or "Doday" in body


async def test_404_json_for_api_clients(client: AsyncClient) -> None:
    """HTMX / API запросы без Accept text/html — не получают HTML."""
    resp = await client.get(
        "/lessio/blog/missing",
        headers={"accept": "application/json"},
    )
    assert resp.status_code == 404
    # Не должен быть HTML
    assert "<html" not in resp.text.lower()
