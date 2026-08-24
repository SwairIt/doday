"""Smoke test for the countdown pins widget on /today."""

from httpx import AsyncClient


async def test_pins_widget_present_on_today(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # The widget renders both the empty state hint and the localStorage key.
    assert "doday-countdowns" in body
    assert "Закрепить дату" in body
