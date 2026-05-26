"""Bulk-selection "select all" — store methods, Ctrl/Cmd+A hotkey, and the
bulk-bar button are present on app pages. Behaviour is Playwright-verified."""

from httpx import AsyncClient


async def test_select_all_store_and_hotkey_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    # Store gained the select-all methods…
    assert "selectAll()" in body
    assert "toggleAll()" in body
    assert "visibleIds()" in body
    # …and the Ctrl/Cmd+A hotkey is wired.
    assert "e.key.toLowerCase() === 'a'" in body


async def test_select_all_button_in_bulk_bar(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "$store.selection.selectAll()" in body
    assert "Выделить все видимые" in body
