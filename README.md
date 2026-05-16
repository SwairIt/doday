# Doday

> A focused to-do app that lives inside Telegram. Built by a 15-year-old.

[![Tests](https://github.com/SwairIt/doday/actions/workflows/test.yml/badge.svg)](https://github.com/SwairIt/doday/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[Live → getdoday.ru](https://getdoday.ru)** · **[Telegram bot → @DodayTaskBot](https://t.me/DodayTaskBot)** · *(Russian-language UI)*

![Doday Mini App demo](docs/assets/demo.gif)

> _The GIF placeholder above will be filled with a 30-second demo of the Mini App (swipe-actions, Pomodoro, comments). See [docs/assets/HOW_TO_RECORD.md](docs/assets/HOW_TO_RECORD.md) for how to record it._

## What it is

A todo-list with three surfaces sharing one backend:

- **Web app** — fast HTMX-driven UI. Inbox, Today, Upcoming, Calendar, Projects with sections, labels, recurring tasks, Pomodoro timer, basic stats.
- **Telegram Mini App** — full feature parity in a bottom-sheet UI. Swipe-actions, drag-to-reorder, native haptics, light/dark/system theme.
- **Telegram bot** — entry point that opens the Mini App. Quick add via `/add`, daily morning digest, reminders.

Plus **shared projects** in Todoist style — invite teammates by email, they join via a one-click link, everyone sees + edits + comments + can be assigned tasks.

100% free, no ads, no subscriptions yet (`BETA_FREE_FOR_ALL=true`). Early users will keep Pro forever when paid plans return.

## Why it might be interesting

- **Zero React, zero JS build step.** FastAPI + Jinja + HTMX + Alpine.js + Tailwind CDN. SPA feel without a bundler. Sub-100KB JS payload.
- **`mypy --strict` across 38 modules, `ruff` with `E,F,I,UP,B,S,A,RUF`, `pre-commit` enforces both on every commit.** 650+ tests, CI on every push.
- **One-line deploy: `git push`.** A cron-poll on the VPS pulls `master` every 60s, runs migrations, restarts uvicorn.
- **Authorization model is centrally enforced in 3 service functions** — `get_project` / `get_task` / `get_section`. Every router calls them with `user.id`. Sharing was added without touching 40 routers.
- **Telegram Mini App auth via `initData` HMAC validation** + cookie session bridge — Mini App and web share the same auth layer.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI 0.115 · async SQLAlchemy 2.0 · Pydantic v2 |
| Database | PostgreSQL 16 (asyncpg) · Alembic |
| Templates | Jinja2 (server-side) |
| Interactivity | HTMX 2 · Alpine.js |
| Styles | Tailwind CSS (CDN — no build) |
| Telegram | python-telegram-bot v21 · WebApp SDK |
| Email | aiosmtplib |
| Auth | argon2-cffi · itsdangerous (signed session cookie) |
| Observability | structlog (JSON) · Sentry · Yandex Metrika |
| Dev tools | uv · ruff · mypy --strict · pre-commit |
| CI | GitHub Actions |

## Local setup

Prerequisites: [uv](https://docs.astral.sh/uv/), Python 3.12+, a running PostgreSQL.

1. Clone + copy `.env.example` → `.env`:
   - `APP_SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `DATABASE_URL` — your Postgres URL
   - `TEST_DATABASE_URL` — separate DB, truncated between test functions
   - `SMTP_*` — defaults assume a local debug SMTP on `localhost:1025`. For real email, point to a real provider.

2. Create the databases:
   ```sql
   CREATE USER doday WITH PASSWORD 'changeme';
   CREATE DATABASE doday OWNER doday;
   CREATE DATABASE doday_test OWNER doday;
   ```

3. Install + migrate + run:
   ```bash
   uv sync
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```

4. (Optional) Capture verification emails locally:
   ```bash
   uv run python -m aiosmtpd -n -l localhost:1025
   ```

5. Open `http://localhost:8000` → register → check the SMTP terminal for the verify link → log in.

## Project structure

```
app/
├── auth/             registration, login, sessions, email verify
├── tasks/            tasks: CRUD, recurrence, subtasks, completion
├── projects/         projects + sections + sharing (members + invitations)
├── comments/         comments on tasks and subtasks
├── labels/           labels per task
├── pomodoro/         persistent Pomodoro timer (sessions in DB)
├── reminders/        per-task scheduled reminders
├── stats/            daily-streak + per-priority + per-project stats
├── miniapp/          Telegram Mini App router + initData auth + JS bundle
├── telegram/         bot: long-polling worker + commands + JobQueue
├── school/           optional Russian school-diary integration (dormant)
├── views/            HTMX page handlers
├── pages/            static pages (landing, privacy, pricing)
├── billing/          tier definitions (paused via BETA_FREE_FOR_ALL)
├── digest/           daily email digest (cron-triggered)
├── help/             in-app help drawer + articles
├── admin/            admin-only routes
├── backup/           JSON/CSV user-data export + import
├── profile/          settings endpoints (theme, password, account delete)
├── sections/         sections within projects
└── templates/        Jinja2 (web + miniapp + email)

alembic/versions/     30+ migrations
tests/                pytest suite (TRUNCATE between functions, mode=auto)
docs/superpowers/     all design specs + implementation plans
scripts/smoke_test.py 23-endpoint smoke test against prod
```

## Quality bar

Every commit must pass:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy --strict app/ scripts/
uv run python scripts/lint_templates.py
uv run pytest -q
```

`pre-commit install` wires the first four into a git hook. Migrations are forward-only — destructive ones (drop table / drop column) raise `NotImplementedError` on `downgrade()`; restore from a pre-cleanup tag + `pg_dump` if needed.

## Deployment model

There is one VPS. A cron job runs `/var/www/.../deploy-poll.sh` every minute:

1. `git fetch origin master`
2. If `HEAD != origin/master`: `git reset --hard origin/master`, `alembic upgrade head`, kill uvicorn on `:8011`, restart.

End-to-end deploy: `git push` → live in ~60 seconds. Smoke test (`scripts/smoke_test.py`) hits 23 critical endpoints and confirms `200`/`303`/`401` per expectation.

## Contributing

PRs welcome. Before submitting:

- Run the full quality bar above.
- Add tests for any new behavior — service-layer tests are preferred over endpoint tests where possible.
- Follow the per-feature folder pattern (`app/<feature>/{router,service,models,schemas}.py`).
- Keep the file you touch focused — if it grows past ~600 lines, splitting it is fair game.
- Commit messages in Russian past-tense are how this repo is written (Russian-speaking author) but English is fine for PRs.

Open an issue first for anything bigger than a bug-fix — happy to discuss scope.

## License

MIT — see [LICENSE](LICENSE).

---

## По-русски

Doday — это бесплатный to-do app, который живёт прямо в Telegram. Web + Mini App + бот.

- **Сайт:** [getdoday.ru](https://getdoday.ru)
- **Бот:** [@DodayTaskBot](https://t.me/DodayTaskBot) → тапни menu-кнопку «Doday» → откроется Mini App
- **Open source:** этот репо, лицензия MIT
- **Бесплатно** — без рекламы и подписок (бета). Ранние юзеры останутся на Pro навсегда, когда оплата вернётся.

Все Pro-фичи сейчас бесплатно для всех — `BETA_FREE_FOR_ALL=true` в проде.

История проекта, технические детали и грабли описаны в Хабр-статье — ссылка появится тут после публикации.
