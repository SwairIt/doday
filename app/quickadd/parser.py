"""Natural-language parser for the quick-add input.

Takes a free-form Russian string like "Купить молоко завтра !! @home"
and returns a structured `ParsedQuickAdd` with extracted due date, priority,
project hint, and label names.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.tasks.models import TaskPriority

_BANGS_TO_PRIORITY = {
    1: TaskPriority.P4,
    2: TaskPriority.P3,
    3: TaskPriority.P2,
    4: TaskPriority.P1,
}

_WEEKDAYS_RU: dict[str, int] = {
    "пн": 0,
    "понедельник": 0,
    "вт": 1,
    "вторник": 1,
    "ср": 2,
    "среда": 2,
    "чт": 3,
    "четверг": 3,
    "пт": 4,
    "пятница": 4,
    "сб": 5,
    "суббота": 5,
    "вс": 6,
    "воскресенье": 6,
}


@dataclass
class ParsedQuickAdd:
    title: str
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.P4
    project_name: str | None = None
    label_names: list[str] = field(default_factory=list)


def _eod(d: date) -> datetime:
    """Combine date with 23:59 UTC — our 'date-only' due_at convention."""
    return datetime(d.year, d.month, d.day, 23, 59, tzinfo=UTC)


def parse_quick_add(text: str, *, now: datetime | None = None) -> ParsedQuickAdd:
    if now is None:
        now = datetime.now(UTC)
    today = now.date()
    text = text.strip()

    # Priority: trailing !{1..4}
    priority = TaskPriority.P4
    m = re.search(r"(!{1,4})\s*$", text)
    if m:
        priority = _BANGS_TO_PRIORITY[len(m.group(1))]
        text = text[: m.start()].rstrip()

    # Project hint: #word (first occurrence)
    project_name: str | None = None
    pm = re.search(r"(?<!\w)#(\S+)", text)
    if pm:
        project_name = pm.group(1)
        text = (text[: pm.start()] + text[pm.end() :]).strip()

    # Labels: every @word
    label_names: list[str] = [m.group(1) for m in re.finditer(r"(?<!\w)@(\S+)", text)]
    text = re.sub(r"(?<!\w)@\S+", "", text).strip()

    # Date: phrases first, then weekday, then dd.mm[.yy]
    due_at: datetime | None = None

    for word, target_date in (
        ("сегодня", today),
        ("завтра", today + timedelta(days=1)),
        ("послезавтра", today + timedelta(days=2)),
    ):
        wm = re.search(rf"(?i)\b{word}\b", text)
        if wm:
            due_at = _eod(target_date)
            text = (text[: wm.start()] + text[wm.end() :]).strip()
            break

    if due_at is None:
        for word, weekday in _WEEKDAYS_RU.items():
            wm = re.search(rf"(?i)\b{word}\b", text)
            if wm:
                days_ahead = (weekday - today.weekday()) % 7 or 7
                due_at = _eod(today + timedelta(days=days_ahead))
                text = (text[: wm.start()] + text[wm.end() :]).strip()
                break

    if due_at is None:
        dm = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b", text)
        if dm:
            try:
                day = int(dm.group(1))
                month = int(dm.group(2))
                year = int(dm.group(3)) if dm.group(3) else today.year
                if year < 100:
                    year += 2000
                target = date(year, month, day)
                if not dm.group(3) and target < today:
                    target = date(year + 1, month, day)
                due_at = _eod(target)
                text = (text[: dm.start()] + text[dm.end() :]).strip()
            except ValueError:
                pass  # invalid date — leave the literal in title

    title = re.sub(r"\s+", " ", text).strip() or "(без названия)"

    return ParsedQuickAdd(
        title=title,
        due_at=due_at,
        priority=priority,
        project_name=project_name,
        label_names=label_names,
    )
