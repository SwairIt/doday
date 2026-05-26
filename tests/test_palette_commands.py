"""The ⌘K palette doubles as a navigation launcher — quick-commands are present
in the rendered app shell. Filtering/click is Playwright-verified."""

from httpx import AsyncClient


async def test_palette_has_nav_commands(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    # The launcher command list (rendered in the global palette in app_base).
    assert "Перейти" in body
    assert "matchedCommands" in body
    assert "/doday/app/team" in body
    assert "/doday/app/activity" in body
    assert "Команда" in body
