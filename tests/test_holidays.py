"""Tests for the Russian school holidays calendar."""

from datetime import date

from httpx import AsyncClient

from app.school.holidays import current_holiday, next_holiday


def test_winter_holiday_jan_5_2026() -> None:
    h = current_holiday(date(2026, 1, 5))
    assert h is not None
    assert "Зимние" in h["name"]


def test_first_day_of_class_no_holiday() -> None:
    # Sept 1 is always classes day in RU
    assert current_holiday(date(2025, 9, 1)) is None


def test_next_holiday_skips_current() -> None:
    """If we're inside a holiday, next_holiday should still return a future one."""
    nxt = next_holiday(date(2026, 1, 5))
    assert nxt is not None
    assert nxt["start"] > date(2026, 1, 5)


def test_summer_2026_long() -> None:
    h = current_holiday(date(2026, 7, 15))
    assert h is not None
    assert "Летние" in h["name"]


async def test_holiday_endpoint_today(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/school/holiday")
    assert response.status_code == 200
    body = response.json()
    assert "current" in body
    assert "next" in body
    assert "days_until_next" in body
