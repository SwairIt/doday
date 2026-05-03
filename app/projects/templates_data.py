"""Built-in project templates — readymade structures for common use-cases.

Each template defines: a key, a display name, an icon emoji, a color, a list of
sections (with ordered tasks), and a list of tasks without a section. When
instantiated, sections are created in order and tasks are spawned with optional
relative due-date offsets in days.
"""

from typing import TypedDict


class TemplateTask(TypedDict, total=False):
    title: str
    priority: str  # 'p1' | 'p2' | 'p3' | 'p4'
    due_offset_days: int  # days from instantiation


class TemplateSection(TypedDict):
    name: str
    tasks: list[TemplateTask]


class ProjectTemplate(TypedDict):
    key: str
    name: str
    icon: str
    color: str
    description: str
    sections: list[TemplateSection]
    loose_tasks: list[TemplateTask]


TEMPLATES: list[ProjectTemplate] = [
    {
        "key": "weekly-planning",
        "name": "Планирование недели",
        "icon": "📅",
        "color": "violet",
        "description": "Канбан-доска с типичными колонками для недельного планирования.",
        "sections": [
            {
                "name": "К выполнению",
                "tasks": [
                    {"title": "Спланировать неделю в воскресенье", "priority": "p2"},
                    {"title": "Записать главную цель недели", "priority": "p1"},
                ],
            },
            {"name": "В работе", "tasks": []},
            {"name": "На паузе", "tasks": []},
            {
                "name": "Готово",
                "tasks": [
                    {"title": "Создать проект из шаблона", "priority": "p4"},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "personal-life",
        "name": "Личная жизнь",
        "icon": "🌱",
        "color": "emerald",
        "description": "Привычки, здоровье, финансы — всё, чем стоит заниматься регулярно.",
        "sections": [
            {
                "name": "Здоровье",
                "tasks": [
                    {"title": "Записаться к врачу на чек-ап", "priority": "p2"},
                    {"title": "30 минут активности сегодня", "priority": "p3"},
                ],
            },
            {
                "name": "Финансы",
                "tasks": [
                    {"title": "Свести бюджет за месяц", "priority": "p2"},
                    {"title": "Перевести деньги на накопительный", "priority": "p3"},
                ],
            },
            {
                "name": "Дом",
                "tasks": [
                    {"title": "Генеральная уборка раз в неделю", "priority": "p4"},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "work-week",
        "name": "Рабочая неделя",
        "icon": "💼",
        "color": "sky",
        "description": "Структура для офисного или удалённого сотрудника.",
        "sections": [
            {
                "name": "Понедельник",
                "tasks": [
                    {"title": "Планёрка с командой", "priority": "p2", "due_offset_days": 0},
                    {"title": "Разобрать почту", "priority": "p3"},
                ],
            },
            {"name": "Вторник", "tasks": []},
            {"name": "Среда", "tasks": []},
            {"name": "Четверг", "tasks": []},
            {
                "name": "Пятница",
                "tasks": [
                    {"title": "Подвести итоги недели", "priority": "p2"},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "school",
        "name": "Учёба",
        "icon": "🎓",
        "color": "amber",
        "description": "Домашка, проекты, экзамены — для школьников и студентов.",
        "sections": [
            {
                "name": "Домашка",
                "tasks": [
                    {"title": "Сделать уроки на завтра", "priority": "p1", "due_offset_days": 0},
                ],
            },
            {
                "name": "Проекты",
                "tasks": [
                    {"title": "Дописать реферат", "priority": "p2", "due_offset_days": 7},
                ],
            },
            {
                "name": "Экзамены",
                "tasks": [
                    {"title": "Составить план подготовки", "priority": "p1"},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "moving",
        "name": "Переезд",
        "icon": "📦",
        "color": "rose",
        "description": "Чек-лист для большого переезда — ничего не забыть.",
        "sections": [
            {
                "name": "За месяц до переезда",
                "tasks": [
                    {"title": "Найти транспортную компанию", "priority": "p1"},
                    {"title": "Заказать коробки и упаковку", "priority": "p2"},
                    {"title": "Сообщить арендодателю", "priority": "p1"},
                ],
            },
            {
                "name": "За неделю",
                "tasks": [
                    {"title": "Упаковать вещи по комнатам", "priority": "p2"},
                    {"title": "Отключить интернет/коммуналку", "priority": "p2"},
                    {"title": "Убраться в старой квартире", "priority": "p3"},
                ],
            },
            {
                "name": "В день переезда",
                "tasks": [
                    {"title": "Сдать ключи", "priority": "p1"},
                    {"title": "Проверить, что ничего не забыто", "priority": "p1"},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "team-sprint",
        "name": "Спринт команды",
        "icon": "🏃",
        "color": "indigo",
        "description": "Двухнедельный спринт для product/dev команды.",
        "sections": [
            {
                "name": "Бэклог",
                "tasks": [
                    {"title": "Сгруппировать задачи по эпикам", "priority": "p3"},
                ],
            },
            {
                "name": "В спринте",
                "tasks": [
                    {"title": "Планирование (понедельник)", "priority": "p2"},
                ],
            },
            {"name": "В работе", "tasks": []},
            {"name": "Ревью", "tasks": []},
            {
                "name": "Готово",
                "tasks": [
                    {"title": "Демо в конце спринта", "priority": "p2", "due_offset_days": 14},
                    {"title": "Ретро", "priority": "p2", "due_offset_days": 14},
                ],
            },
        ],
        "loose_tasks": [],
    },
    {
        "key": "content-calendar",
        "name": "Контент-календарь",
        "icon": "📝",
        "color": "fuchsia",
        "description": "Для блогеров и SMM-щиков — публикации по статусу.",
        "sections": [
            {"name": "Идеи", "tasks": [{"title": "Накидать темы на месяц", "priority": "p2"}]},
            {"name": "В работе", "tasks": []},
            {"name": "На согласовании", "tasks": []},
            {"name": "Опубликовано", "tasks": []},
        ],
        "loose_tasks": [],
    },
    {
        "key": "trip",
        "name": "Поездка",
        "icon": "✈️",
        "color": "cyan",
        "description": "Подготовка к путешествию — документы, бронь, чемодан.",
        "sections": [
            {
                "name": "Документы и брони",
                "tasks": [
                    {"title": "Купить билеты", "priority": "p1"},
                    {"title": "Забронировать жильё", "priority": "p1"},
                    {"title": "Оформить страховку", "priority": "p2"},
                    {"title": "Проверить срок действия паспорта", "priority": "p1"},
                ],
            },
            {
                "name": "Чемодан",
                "tasks": [
                    {"title": "Список вещей", "priority": "p3"},
                    {"title": "Зарядки и переходники", "priority": "p3"},
                ],
            },
            {
                "name": "Перед вылетом",
                "tasks": [
                    {"title": "Онлайн-регистрация за 24 часа", "priority": "p2"},
                    {"title": "Заказать такси в аэропорт", "priority": "p2"},
                ],
            },
        ],
        "loose_tasks": [],
    },
]


def get_template(key: str) -> ProjectTemplate | None:
    return next((t for t in TEMPLATES if t["key"] == key), None)
