"""Smoke test for the Monday week-plan widget."""

from httpx import AsyncClient


async def test_widget_markup_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    # Markup is always rendered server-side; visibility is JS-gated to Mon-Tue.
    assert "doday-week-plan-" in body
    assert "3 главные вещи" in body
