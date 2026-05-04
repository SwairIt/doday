"""Russian school holidays — typical dates for 2024-2025 and 2025-2026 учебных лет.

Real schools vary by region/triadic vs quarter system; the dates here mirror
the most common single-region schedule (Moscow oblast quarter-system).
Override per-user later if it ever matters.
"""

from datetime import date
from typing import TypedDict


class HolidayWindow(TypedDict):
    name: str
    start: date
    end: date  # inclusive


# Cover plenty of academic years so the widget keeps making sense across rollovers.
HOLIDAY_WINDOWS: list[HolidayWindow] = [
    {"name": "Осенние каникулы", "start": date(2024, 10, 28), "end": date(2024, 11, 5)},
    {"name": "Зимние каникулы", "start": date(2024, 12, 28), "end": date(2025, 1, 8)},
    {"name": "Весенние каникулы", "start": date(2025, 3, 24), "end": date(2025, 3, 30)},
    {"name": "Летние каникулы", "start": date(2025, 6, 1), "end": date(2025, 8, 31)},
    {"name": "Осенние каникулы", "start": date(2025, 10, 27), "end": date(2025, 11, 4)},
    {"name": "Зимние каникулы", "start": date(2025, 12, 29), "end": date(2026, 1, 11)},
    {"name": "Весенние каникулы", "start": date(2026, 3, 23), "end": date(2026, 3, 29)},
    {"name": "Летние каникулы", "start": date(2026, 6, 1), "end": date(2026, 8, 31)},
    {"name": "Осенние каникулы", "start": date(2026, 10, 26), "end": date(2026, 11, 3)},
    {"name": "Зимние каникулы", "start": date(2026, 12, 28), "end": date(2027, 1, 10)},
    {"name": "Весенние каникулы", "start": date(2027, 3, 22), "end": date(2027, 3, 28)},
    {"name": "Летние каникулы", "start": date(2027, 6, 1), "end": date(2027, 8, 31)},
]


def current_holiday(today: date) -> HolidayWindow | None:
    """Return the holiday window covering `today`, if any."""
    for win in HOLIDAY_WINDOWS:
        if win["start"] <= today <= win["end"]:
            return win
    return None


def next_holiday(today: date) -> HolidayWindow | None:
    """Return the closest upcoming holiday (start > today)."""
    upcoming = [w for w in HOLIDAY_WINDOWS if w["start"] > today]
    return min(upcoming, key=lambda w: w["start"]) if upcoming else None
