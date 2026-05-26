"""Tests for the in-page reminder agent (browser Notification API poller)."""

from httpx import AsyncClient


async def test_reminders_partial_included(logged_in_client: AsyncClient) -> None:
    """The reminder script is loaded on every app page."""
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "doday-reminded-ids-v1" in body
    assert "/api/tasks/today" in body


async def test_reminders_can_be_disabled(logged_in_client: AsyncClient) -> None:
    """The opt-out localStorage key is honored before any poll fires."""
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "doday-reminders-off" in body
