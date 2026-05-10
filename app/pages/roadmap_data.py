"""Roadmap shown on /roadmap. 3 секции — Now / Next / Maybe.

«Now» — над чем работаем прямо сейчас (есть commit-активность).
«Next» — обозримые следующие 2-3 месяца, с понятным acceptance.
«Maybe» — идеи без коммитмента; могут переехать в Next или удалиться.

Прозрачность намеренная: Habr ценит «честный roadmap» больше чем
«будет всё и сразу». Если идея застряла на «Maybe» полгода — её
надо или оживить, или удалить.
"""

from typing import TypedDict


class Item(TypedDict):
    title: str
    description: str


class Section(TypedDict):
    name: str  # «Сейчас», «Следующее», «Может быть»
    color: str  # tailwind class — emerald/violet/slate
    items: list[Item]


SECTIONS: list[Section] = [
    {
        "name": "Сейчас",
        "color": "emerald",
        "items": [
            {
                "title": "Telegram Mini App",
                "description": "Полноценный апп прямо в Telegram-клиенте: "
                "Today, Inbox, календарь, swipe-actions, привязка к "
                "аккаунту через initData. Auto-theming под Telegram-тему.",
            },
            {
                "title": "Email-дайджест на утро",
                "description": "Письмо в 7:00 МСК со списком задач на день. "
                "Код готов, ждёт SMTP-провайдера на проде (Resend / Brevo).",
            },
            {
                "title": "Sentry observability",
                "description": "Подключён, ждёт DSN от админа. Без него — "
                "вслепую узнаём про баги от пользователей.",
            },
        ],
    },
    {
        "name": "Следующее",
        "color": "violet",
        "items": [
            {
                "title": "ЮKassa подписки",
                "description": "Когда наберётся ~50 платящих юзеров. "
                "Ранние grandfather'ятся в Pro навсегда — не доплачивают.",
            },
            {
                "title": "Family-тариф с parent dashboard",
                "description": "Родитель видит прогресс ребёнка по "
                "урокам / домашке. Один счёт на 5 аккаунтов.",
            },
            {
                "title": "Userscript для МО / МЭШ",
                "description": "Авто-синк школьной домашки из Школьного "
                "портала Московской области и МЭШ. Первый чан — после "
                "Mini App.",
            },
            {
                "title": "Push-уведомления через Web Push",
                "description": "На устройства где нет Telegram. iOS Safari "
                "16+ и Android Chrome поддерживают.",
            },
            {
                "title": "Совместные проекты",
                "description": "Пригласить друга в проект — оба видят "
                "задачи, могут отмечать. Без full-blown teams — для "
                "семьи / пары / соседей по комнате.",
            },
        ],
    },
    {
        "name": "Может быть",
        "color": "slate",
        "items": [
            {
                "title": "Voice quick-add",
                "description": "Записать голосом задачу через Whisper.cpp. "
                "Сложно делать офлайн на клиенте; на сервере — нужны GPU.",
            },
            {
                "title": "Десктоп-клиент",
                "description": "Electron / Tauri обёртка над PWA. Работает "
                "и так через PWA install — нативный клиент даст лишь "
                "global hotkeys и tray-иконку.",
            },
            {
                "title": "Markdown-заметки в задачах",
                "description": "Не TaskRichEditor (это Notion), а просто "
                "поле «описание» с базовым markdown. Проблема: где "
                "грань между todo и note?",
            },
            {
                "title": "Тёмные подтемы",
                "description": "Не только Forest/Minimal, а ещё 3-5 "
                "вариантов акцента. Низкий приоритет — большинство "
                "юзеров никогда не открывают theme picker.",
            },
            {
                "title": "Командная подписка для классов",
                "description": "Учитель → 30 ребятам аккаунты с общим "
                "проектом «Класс 9А». Нужно решить вопросы с ПДн "
                "несовершеннолетних.",
            },
        ],
    },
]
