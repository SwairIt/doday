"""Changelog entries shown on /changelog. Newest first.

Каждая запись — публичный апдейт. Internal-чанки и хот-фиксы не сюда —
сюда только то что пользователь почувствует. Источник: коммит-логи + майлстоны
из PROGRESS.md, переведённые на пользователе-понятный язык.
"""

from typing import TypedDict


class Entry(TypedDict):
    date: str  # ISO 8601 (YYYY-MM-DD)
    version: str  # человеко-читаемая версия — «v0.7» или «beta»
    title: str
    notes: list[str]


ENTRIES: list[Entry] = [
    {
        "date": "2026-05-11",
        "version": "v0.8 — beta",
        "title": "Habr-launch — все функции бесплатно",
        "notes": [
            "🚀 Бета-режим: все функции бесплатно для всех юзеров. Ранние "
            "получат Pro навсегда когда введём оплату",
            "Sentry для отлова крашей (если что-то ломается — узнаём сразу, "
            "а не от злого комментатора)",
            "Telegram-канал для community и анонсов в футере",
            "Страница /changelog — список апдейтов",
            "Страница /roadmap — куда движемся",
        ],
    },
    {
        "date": "2026-05-10",
        "version": "v0.7",
        "title": "Telegram Mini App в разработке + полный mobile polish",
        "notes": [
            "Mini App в Telegram — в активной разработке (TG initData auth, "
            "bottom-nav, swipe-actions). Анонс в TG-канале",
            "Полный адаптивный аудит 320/375/414/768/1280 пройден на 30+ "
            "страницах — нет горизонтального overflow ни на одном "
            "viewport",
            "Кнопки FAB больше не перекрывают kebab-меню задач",
            "Toolbar Сортировка/Группа/Готово не «жмётся» на 320px",
            "Lonely-kebab у задач без тегов — kebab inline в title-row",
            "Красивая 404-страница с CTA «вернуться домой»",
            "Skip-to-content link для screen-reader",
            "Typography: text-wrap balance/pretty для заголовков, "
            "focus-visible ring для всех интерактивных элементов",
        ],
    },
    {
        "date": "2026-05-09",
        "version": "v0.6",
        "title": "Tier-enforcement audit + Pro-темы",
        "notes": [
            "Подписочные фичи строго gated на Pro: email-дайджест, "
            "Telegram-бот, шаблоны проектов «save-as» — Free возвращает "
            "402 Payment Required (открывает upgrade-модалку)",
            "Premium-темы Forest и Minimal активируются с учётом trial — не только tier",
            "Корзина: 14 дней Free / 30 дней Pro (раньше всем 30)",
            "FAQ обновлён под актуальные фичи и тарифы",
        ],
    },
    {
        "date": "2026-05-08",
        "version": "v0.5",
        "title": "Pre-launch фаза 1 — маркетинг-готовность",
        "notes": [
            "Контент-аудит landing: hero/CTA/3 шага/comparison-карточки",
            "Pricing редизайн с Annual/Monthly toggle и FAQ",
            "10 help-статей закрыли основные вопросы новичков",
            "Privacy-politics страница (РКН-friendly)",
        ],
    },
    {
        "date": "2026-05-07",
        "version": "v0.4",
        "title": "Telegram-бот + admin-панель",
        "notes": [
            "Telegram-бот: команды /add /today /upcoming /done /unlink + "
            "natural-language парсер (даты, приоритеты, лейблы)",
            "Привязка чата к Doday-аккаунту через одноразовый токен в Профиле",
            "Root-аккаунт + /app/root админ-панель с метриками, жалобами, token-API для интеграций",
            "Кнопка «🐞 Сообщить о проблеме» в help-drawer",
        ],
    },
    {
        "date": "2026-05-06",
        "version": "v0.3",
        "title": "PWA + Yandex.Metrika + auto-deploy",
        "notes": [
            "PWA-манифест с safe-area-inset для iOS-устройств с notch",
            "Можно установить на главный экран iPhone/Android — выглядит как нативное приложение",
            "Yandex.Metrika подключена для аналитики (без heatmap'ов и "
            "записи сессий — privacy first)",
            "Auto-deploy на прод через cron-poll: пуш в master → деплой за минуту",
        ],
    },
    {
        "date": "2026-05-05",
        "version": "v0.2",
        "title": "Audience-aware welcome + школьное расписание",
        "notes": [
            "При регистрации спрашиваем «школа / работа / личное» — "
            "стартовые задачи и сайдбар адаптируются",
            "Школьники получают «Расписание» (привязка к парам), компании "
            "— виджет stand-up, личное — без bloat",
            "Редизайн меню сайдбара под аудиенс-режим",
        ],
    },
    {
        "date": "2026-05-03",
        "version": "v0.1",
        "title": "Doday — публичная альфа",
        "notes": [
            "Запуск под брендом Doday. Раньше был «SchoolTodo» — но продукт давно перерос школу",
            "60+ фич: проекты, секции, лейблы, фильтры, календарь, граф "
            "связей, помодоро, привычки, статистика",
            "Импорт-экспорт JSON / CSV / Markdown / .ics",
            "Тёмная и светлая тема, 2 акцентных цвета базово",
        ],
    },
]
