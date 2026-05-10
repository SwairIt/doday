"""Telegram Mini App: web-app внутри Telegram-клиента.

Открывается из бота через menu-button или /app команду. Auth — через
Telegram WebApp initData (HMAC-подпись с bot token), лукап в
telegram_links → session-cookie. Auto-themed под клиента.

Архитектура: HTMX + Alpine + Tailwind, тот же что в веб-апе. URL-префикс
`/miniapp/`. Отдельный layout `miniapp/_base.html` без topbar/sidebar.
"""
