"""Tests for the page-local filter (Ctrl+F / `/` live-search on visible task rows)."""

from httpx import AsyncClient


async def test_page_filter_partial_included(logged_in_client: AsyncClient) -> None:
    """The filter widget is mounted globally on every app page."""
    body = (await logged_in_client.get("/doday/app/today")).text
    # The widget watches Ctrl+F / `/` and filters rows by innerText
    assert "Фильтр на этой странице" in body
    assert "task-wrap-" in body


async def test_page_filter_intercepts_ctrl_f(logged_in_client: AsyncClient) -> None:
    """The widget hooks both Ctrl/Cmd+F and the slash key."""
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "ctrlKey" in body
    assert "metaKey" in body
    assert "key === '/'" in body or 'key === "/"' in body
