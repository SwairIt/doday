"""Built-in list of Russian school subjects with friendly emoji + colour.

Used by the schedule grid (subject dropdown) and in school-portal-integration mode.
"""

from typing import TypedDict


class Subject(TypedDict):
    code: str
    name: str
    emoji: str
    color: str  # tailwind shade name


SUBJECTS: list[Subject] = [
    {"code": "math", "name": "Математика", "emoji": "🔢", "color": "violet"},
    {"code": "algebra", "name": "Алгебра", "emoji": "➗", "color": "violet"},
    {"code": "geometry", "name": "Геометрия", "emoji": "📐", "color": "fuchsia"},
    {"code": "rus", "name": "Русский язык", "emoji": "📝", "color": "rose"},
    {"code": "lit", "name": "Литература", "emoji": "📖", "color": "amber"},
    {"code": "eng", "name": "Английский", "emoji": "🇬🇧", "color": "sky"},
    {"code": "history", "name": "История", "emoji": "📜", "color": "orange"},
    {"code": "social", "name": "Обществознание", "emoji": "🏛️", "color": "yellow"},
    {"code": "geo", "name": "География", "emoji": "🌍", "color": "emerald"},
    {"code": "biology", "name": "Биология", "emoji": "🧬", "color": "green"},
    {"code": "physics", "name": "Физика", "emoji": "⚛️", "color": "blue"},
    {"code": "chemistry", "name": "Химия", "emoji": "⚗️", "color": "teal"},
    {"code": "informatics", "name": "Информатика", "emoji": "💻", "color": "indigo"},
    {"code": "pe", "name": "Физкультура", "emoji": "🏃", "color": "lime"},
    {"code": "art", "name": "ИЗО", "emoji": "🎨", "color": "pink"},
    {"code": "music", "name": "Музыка", "emoji": "🎵", "color": "purple"},
    {"code": "obj", "name": "ОБЖ", "emoji": "⛑️", "color": "red"},
    {"code": "tech", "name": "Технология", "emoji": "🔧", "color": "stone"},
    {"code": "free", "name": "Окно", "emoji": "☕", "color": "zinc"},
]


def get_subject(code: str) -> Subject | None:
    return next((s for s in SUBJECTS if s["code"] == code), None)


def detect_subject(title: str) -> Subject | None:
    """Best-effort match: scan a task title for any subject name as a substring.

    Lowercased so 'Алгебра — параграф 5' matches 'Алгебра'. Returns the first
    match in SUBJECTS order — order matters for short names that are prefixes
    of longer ones (e.g. 'История' vs nothing). 'Окно' is excluded because
    it's a schedule placeholder, not a real subject for tasks.
    """
    t = title.lower()
    for s in SUBJECTS:
        if s["code"] == "free":
            continue
        if s["name"].lower() in t:
            return s
    return None


WEEKDAY_SHORT_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAY_FULL_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]
