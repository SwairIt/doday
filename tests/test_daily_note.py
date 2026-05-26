"""Smoke test for the daily note widget on /today."""

from httpx import AsyncClient


async def test_daily_note_markup_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/today")).text
    assert "Заметка дня" in body
    assert "только в этом браузере" in body
    assert "doday-note-" in body  # the localStorage key prefix
