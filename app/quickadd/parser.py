"""Natural-language parser for the quick-add input.

Takes a free-form Russian string like "Купить молоко завтра !! @home"
and returns a structured `ParsedQuickAdd` with extracted due date, priority,
project hint, label names and (optional) recurrence.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

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

_WEEKDAYS_RU_ACC: dict[str, int] = {  # accusative — для «каждый <день недели>»
    "понедельник": 0,
    "вторник": 1,
    "среду": 2,
    "четверг": 3,
    "пятницу": 4,
    "субботу": 5,
    "воскресенье": 6,
}

_MONTHS_RU: dict[str, int] = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}  # fmt: skip

# Time-of-day words → (hour, minute). When one of these is present along with
# a date, the date stops being date-only and gets a real wall-clock hour.
_TIMES_OF_DAY: dict[str, tuple[int, int]] = {
    "утром": (9, 0),
    "утра": (9, 0),
    "днём": (13, 0),
    "днем": (13, 0),
    "обед": (13, 0),
    "после обеда": (15, 0),
    "вечером": (20, 0),
    "вечера": (20, 0),
    "ночью": (23, 0),
    "ночи": (23, 0),
}

# Word-level priority hints. Order matters — multi-word longest-first so
# "не срочно" doesn't get clobbered by "срочно".
_PRIORITY_WORDS: list[tuple[str, TaskPriority]] = [
    ("не срочно", TaskPriority.P3),
    ("срочно", TaskPriority.P1),
    ("важно", TaskPriority.P2),
]


@dataclass
class ParsedQuickAdd:
    title: str
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.P4
    project_name: str | None = None
    label_names: list[str] = field(default_factory=list)
    recurrence: str | None = None  # daily / weekly / monthly / yearly
    date_only: bool = True


def _eod(d: date) -> datetime:
    """Combine date with 23:59 UTC — our 'date-only' due_at convention."""
    return datetime(d.year, d.month, d.day, 23, 59, tzinfo=UTC)


def _at(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=UTC)


def parse_quick_add(text: str, *, now: datetime | None = None) -> ParsedQuickAdd:
    if now is None:
        now = datetime.now(UTC)
    today = now.date()
    text = text.strip()

    # Trailing !{1..4} priority hint (highest precedence — explicit beats word).
    priority = TaskPriority.P4
    bang_priority: TaskPriority | None = None
    m = re.search(r"(!{1,4})\s*$", text)
    if m:
        bang_priority = _BANGS_TO_PRIORITY[len(m.group(1))]
        text = text[: m.start()].rstrip()

    # Word-level priority hints (lower precedence than bangs).
    word_priority: TaskPriority | None = None
    for word, prio in _PRIORITY_WORDS:
        wm = re.search(rf"(?i)\b{re.escape(word)}\b", text)
        if wm:
            word_priority = prio
            text = (text[: wm.start()] + text[wm.end() :]).strip()
            break

    if bang_priority is not None:
        priority = bang_priority
    elif word_priority is not None:
        priority = word_priority

    # Project hint: #word (first occurrence)
    project_name: str | None = None
    pm = re.search(r"(?<!\w)#(\S+)", text)
    if pm:
        project_name = pm.group(1)
        text = (text[: pm.start()] + text[pm.end() :]).strip()

    # Labels: every @word
    label_names: list[str] = [m.group(1) for m in re.finditer(r"(?<!\w)@(\S+)", text)]
    text = re.sub(r"(?<!\w)@\S+", "", text).strip()

    # Recurrence: «каждый день/неделю/месяц/год» / «каждую неделю» / «каждый <weekday-acc>».
    recurrence: str | None = None
    rec_pattern = (
        r"(?i)\b(каждый|каждую|каждое)\s+("
        r"день|дня|неделю|недели|месяц|месяца|год|года|"
        + "|".join(_WEEKDAYS_RU_ACC.keys())
        + r")\b"
    )
    rm = re.search(rec_pattern, text)
    if rm:
        unit = rm.group(2).lower()
        if unit in ("день", "дня"):
            recurrence = "daily"
        elif unit in ("неделю", "недели"):
            recurrence = "weekly"
        elif unit in ("месяц", "месяца"):
            recurrence = "monthly"
        elif unit in ("год", "года"):
            recurrence = "yearly"
        elif unit in _WEEKDAYS_RU_ACC:
            recurrence = "weekly"
        text = (text[: rm.start()] + text[rm.end() :]).strip()

    due_at: datetime | None = None
    date_only = True

    # «через N час/часа/часов» — produces a real timestamp, not date-only.
    rh = re.search(r"(?i)\bчерез\s+(\d+)?\s*(час[аов]?|часов)\b", text)
    if rh:
        n = int(rh.group(1)) if rh.group(1) else 1
        due_at = now + timedelta(hours=n)
        date_only = False
        text = (text[: rh.start()] + text[rh.end() :]).strip()

    # «через N минут»
    if due_at is None:
        rmin = re.search(r"(?i)\bчерез\s+(\d+)\s*(минут[ыу]?|мин)\b", text)
        if rmin:
            n = int(rmin.group(1))
            due_at = now + timedelta(minutes=n)
            date_only = False
            text = (text[: rmin.start()] + text[rmin.end() :]).strip()

    # «к выходным» / «на выходных» / «в выходные» → ближайшая суббота
    if due_at is None:
        wkm = re.search(r"(?i)\b(к\s+выходным|на\s+выходных|в\s+выходные)\b", text)
        if wkm:
            ahead = (5 - today.weekday()) % 7  # Saturday = 5
            if ahead == 0:
                ahead = 7
            due_at = _eod(today + timedelta(days=ahead))
            text = (text[: wkm.start()] + text[wkm.end() :]).strip()

    # Date phrases.
    if due_at is None:
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

    # «через N дней/неделю/недели/месяц/месяца»
    if due_at is None:
        rm2 = re.search(
            r"(?i)\bчерез\s+(\d+)?\s*(дн[еья]|день|дней|недел[юия]|месяц[ае]?)\b",
            text,
        )
        if rm2:
            n = int(rm2.group(1)) if rm2.group(1) else 1
            unit = rm2.group(2).lower()
            if unit.startswith("дн") or unit in ("день", "дней"):
                due_at = _eod(today + timedelta(days=n))
            elif unit.startswith("недел"):
                due_at = _eod(today + timedelta(weeks=n))
            elif unit.startswith("месяц"):
                due_at = _eod(today + timedelta(days=30 * n))
            text = (text[: rm2.start()] + text[rm2.end() :]).strip()

    # «N января», «15 декабря» etc.
    if due_at is None:
        mm = re.search(
            r"(?i)\b(\d{1,2})\s+(" + "|".join(_MONTHS_RU.keys()) + r")\b",
            text,
        )
        if mm:
            try:
                day_n = int(mm.group(1))
                month_n = _MONTHS_RU[mm.group(2).lower()]
                year_n = today.year
                target = date(year_n, month_n, day_n)
                if target < today:
                    target = date(year_n + 1, month_n, day_n)
                due_at = _eod(target)
                text = (text[: mm.start()] + text[mm.end() :]).strip()
            except ValueError:
                pass

    if due_at is None:
        for word, weekday in _WEEKDAYS_RU.items():
            wm = re.search(
                rf"(?i)\b(след(?:ующ(?:ий|ая|ее|ую))?\s+)?{word}\b",
                text,
            )
            if wm:
                base_days_ahead = (weekday - today.weekday()) % 7 or 7
                if wm.group(1):
                    base_days_ahead += 7
                due_at = _eod(today + timedelta(days=base_days_ahead))
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

    # Time-of-day word — overlay on existing date (or today if none yet picked).
    # Multi-word phrases scanned first (longest-first) so "после обеда" beats "обед".
    tod_phrases = sorted(_TIMES_OF_DAY.keys(), key=len, reverse=True)
    for phrase in tod_phrases:
        wm = re.search(rf"(?i)\b{re.escape(phrase)}\b", text)
        if wm:
            hh, mm_ = _TIMES_OF_DAY[phrase]
            base = due_at.date() if due_at else today
            due_at = _at(base, hh, mm_)
            date_only = False
            text = (text[: wm.start()] + text[wm.end() :]).strip()
            break

    title = re.sub(r"\s+", " ", text).strip() or "(без названия)"

    return ParsedQuickAdd(
        title=title,
        due_at=due_at,
        priority=priority,
        project_name=project_name,
        label_names=label_names,
        recurrence=recurrence,
        date_only=date_only,
    )
