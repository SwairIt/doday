"""Daily marketing layouts, selected by Moscow time on the server."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True, slots=True)
class LandingSchedule:
    template_name: str
    variant: str
    seconds_until_switch: int | None


def _minutes(value: str, default: int) -> int:
    try:
        hour, minute = value.split(":")
        if len(hour) == 2 and len(minute) == 2 and 0 <= int(hour) < 24 and 0 <= int(minute) < 60:
            return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        pass
    return default


def landing_schedule(
    now: datetime | None = None,
    *,
    mode: str = "schedule",
    light_start: str = "09:00",
    dark_start: str = "19:00",
    system_theme: str = "light",
) -> LandingSchedule:
    moment = now if now is not None else datetime.now(UTC)
    if moment.utcoffset() is None:
        raise ValueError("Landing schedule requires a timezone-aware datetime")
    local = moment.astimezone(MOSCOW)
    light = _minutes(light_start, 9 * 60)
    dark = _minutes(dark_start, 19 * 60)
    if light == dark:
        light, dark = 9 * 60, 19 * 60
    minute = local.hour * 60 + local.minute
    day = light <= minute < dark if light < dark else minute >= light or minute < dark
    seconds_until_switch = None
    if mode in {"light", "dark", "system"}:
        day = mode == "light" or (mode == "system" and system_theme != "dark")
    else:
        boundary = dark if day else light
        next_switch = local.replace(
            hour=boundary // 60, minute=boundary % 60, second=0, microsecond=0
        )
        if next_switch <= local:
            next_switch += timedelta(days=1)
        seconds_until_switch = math.ceil((next_switch - local).total_seconds())
    return LandingSchedule(
        template_name="landing.html" if day else "landing_night.html",
        variant="day" if day else "night",
        seconds_until_switch=seconds_until_switch,
    )
