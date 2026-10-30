"""Schedule boundaries and persisted appearance settings must agree with HTML."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.pages.landing_schedule import landing_schedule


@pytest.mark.parametrize(
    ("moment", "variant", "remaining"),
    [
        ("2026-10-30T05:59:59+00:00", "night", 1),
        ("2026-10-30T06:00:00+00:00", "day", 36000),
        ("2026-10-30T15:59:59+00:00", "day", 1),
        ("2026-10-30T16:00:00+00:00", "night", 50400),
        ("2026-10-30T23:00:00+00:00", "night", 25200),
        ("2026-12-31T23:59:59+03:00", "night", 32401),
    ],
)
def test_default_schedule_uses_moscow_boundaries(moment: str, variant: str, remaining: int) -> None:
    result = landing_schedule(datetime.fromisoformat(moment))
    assert result.variant == variant
    assert result.seconds_until_switch == remaining


@pytest.mark.parametrize(
    ("hour", "light", "dark", "variant"),
    [
        (8, "12:30", "22:45", "night"),
        (13, "12:30", "22:45", "day"),
        (23, "20:00", "04:00", "day"),
        (5, "20:00", "04:00", "night"),
    ],
)
def test_custom_schedule_can_cross_midnight(hour: int, light: str, dark: str, variant: str) -> None:
    now = datetime.fromisoformat(f"2026-10-30T{hour:02}:00:00+03:00")
    assert landing_schedule(now, light_start=light, dark_start=dark).variant == variant


def test_invalid_or_equal_times_fall_back_to_defaults() -> None:
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    for light, dark in [("garbage", "24:90"), ("08:30", "08:30")]:
        assert landing_schedule(now, light_start=light, dark_start=dark) == landing_schedule(now)


@pytest.mark.parametrize(
    ("mode", "system", "variant"),
    [
        ("light", "dark", "day"),
        ("dark", "light", "night"),
        ("system", "dark", "night"),
        ("system", "light", "day"),
    ],
)
async def test_landing_obeys_saved_choice(
    client: AsyncClient, mode: str, system: str, variant: str
) -> None:
    client.cookies.set("doday-theme", mode)
    client.cookies.set("doday-system-theme", system)
    response = await client.get("/")
    assert response.status_code == 200
    assert f'data-landing-variant="{variant}"' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert 'id="appearance-dialog"' in response.text
    assert "data-theme-open" in response.text
    assert (
        f'data-src="/static/landing/doday-in-action{"-dark" if variant == "night" else ""}.mp4"'
        in response.text
    )
    assert 'name="appearance-mode" value="schedule"' in response.text
    if variant == "night":
        assert "particles_fx" not in response.text  # rendered partial, never a template name
        assert "Тудулист, в котором" in response.text


async def test_landing_applies_custom_time_from_cookies(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.pages import router as pages

    moment = datetime.fromisoformat("2026-10-30T10:00:00+03:00")
    monkeypatch.setattr(
        pages, "landing_schedule", lambda **settings: landing_schedule(moment, **settings)
    )
    client.cookies.set("doday-theme", "schedule")
    client.cookies.set("doday-theme-light-start", "11:30")
    client.cookies.set("doday-theme-dark-start", "22:00")
    response = await client.get("/doday")
    assert response.status_code == 200
    assert 'data-landing-variant="night"' in response.text
    client.cookies.set("doday-theme-light-start", "08:00")
    assert 'data-landing-variant="day"' in (await client.get("/")).text
