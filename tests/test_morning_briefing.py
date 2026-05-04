"""Smoke tests for the morning briefing widget on /today."""

from httpx import AsyncClient


async def test_briefing_markup_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # the widget is conditionally shown by the client (4-11 local), but the
    # markup is always rendered server-side — verify presence
    assert "Доброе утро" in body
    assert "🌅" in body


async def test_briefing_picks_up_email_username(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # logged_in_client logs in as logged-in@example.com → username "Logged-in"
    assert "Logged-in" in body
