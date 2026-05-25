"""Lessio — Telegram-кабинет для репетиторов и онлайн-тренеров.

Живёт внутри Doday-репо как отдельный feature-модуль, чтобы переиспользовать
готовую инфру (deploy через cron-poll, БД, Stars-bot @DodayTaskBot, миграции).

Phase: validation (с 2026-05-25). Только лендинг + waitlist пока waitlist не
наберёт ≥100 уникальных подписок. Решение go/pivot/drop — 2026-06-01.

URLs:
- `GET /lessio` — лендинг (Jinja2 + HTMX-форма waitlist)
- `POST /lessio/waitlist` — приём email + niche + pain_point

После валидации (если go): добавляем `/lessio/cabinet/*` (tutor admin),
`/lessio/book/<slug>` (client booking), Telegram-bot handlers через
существующий @DodayTaskBot, новые Stars-продукты `tutor_pro_*` (уже в
app.billing.products).
"""
