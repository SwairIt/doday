"""The focused-task 'a' hotkey assigns to the current user. The PATCH is
Playwright-verified; here we assert the handler + help hint are rendered, and
that the current user's id is exposed via the context menu's data-me."""

from httpx import AsyncClient


async def test_assign_hotkey_rendered(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # Handler patches assigned_to using the id from #task-ctx-menu data-me.
    assert "patchSelected({assigned_to: me})" in body
    assert "data-me=" in body
    # Help overlay documents the hotkey.
    assert "Назначить на меня" in body
