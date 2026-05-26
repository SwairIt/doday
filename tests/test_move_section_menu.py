"""The «Перенести в секцию →» context-menu item must be rendered. The dynamic
section submenu (lazy fetch + PATCH) is verified by Playwright; here we only
assert the server renders the menu item."""

from httpx import AsyncClient


async def test_move_section_item_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert 'data-ctx="move-section"' in body
    assert "Перенести в секцию" in body
