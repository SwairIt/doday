"""Telegram bot — добавление задач из чата без открытия сайта.

Архитектура:
- Юзер на /app/profile → «Подключить Telegram» → POST /api/profile/telegram-link →
  получает t.me/<bot>?start=<one-time-token>.
- Бот ловит /start <token> → заполняет chat_id, обнуляет link_token.
- Дальше команды /add, /today, /done, /upcoming работают через chat_id → user.
- Бот живёт как отдельный systemd-сервис на проде, polling-mode (без webhook).
"""
