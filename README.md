<div align="center">

# Doday

**A focused todo + teams app for the post-subscription era.**
Web · Telegram Mini App · Bot · all sharing one backend.

[![CI](https://github.com/SwairIt/doday/actions/workflows/ci.yml/badge.svg)](https://github.com/SwairIt/doday/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Telegram Stars](https://img.shields.io/badge/payments-Telegram%20Stars%20%E2%AD%90-FFD93D)](https://core.telegram.org/bots/payments-stars)

**[Live → getdoday.ru](https://getdoday.ru)** · **[Bot → @DodayTaskBot](https://t.me/DodayTaskBot)** · **[Pricing](https://getdoday.ru/pricing)** · **[Roadmap](https://getdoday.ru/roadmap)**

</div>

---

## What it is

Doday is a Russian-language todo + team-collaboration app, built by a 15-year-old solo developer ([@SwairIt](https://github.com/SwairIt)) in pair-programming with [Claude Code](https://claude.com/claude-code). It started on May 2nd, 2026 as a "todo for Russian schoolers" and grew into a focused alternative to Todoist with a Telegram-native surface — three weeks of intense daily coding by the time Stars payments shipped.

**Three surfaces, one codebase:**

- **Web app** ([getdoday.ru](https://getdoday.ru)) — desktop-first, HTMX-driven. Inbox, Today, Upcoming, Calendar, projects with sections, labels, recurring tasks, Pomodoro, statistics.
- **Telegram Mini App** — full feature parity in mobile-native bottom-sheet UI. Swipe-actions, drag-to-reorder, haptics.
- **Telegram bot** — `@DodayTaskBot`. Quick-add via `/add`, morning digest, reminders, deeplink to Mini App.

**Team collaboration:** invite anyone by email, they join via one-click link, both edit + comment + get assigned tasks.

**Payments via Telegram Stars** (⭐) — the only legal monetization path I could ship at age 16 (ЮKassa/Stripe/etc. all require 18+).

---

## Why it might be interesting

- **Zero React, zero JS build step.** FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CDN. SPA feel without a bundler. Sub-100KB JS payload on the hot path.
- **`mypy --strict` across the entire app + scripts.** `ruff` rules `E,F,I,UP,B,S,A,RUF`. `pre-commit` enforces both on every commit. CI runs the full test suite (~850 tests) on every push.
- **Authorization is centralized in three service functions** — `get_project / get_task / get_section`. Every router calls them with `user.id`. Team-sharing was added without touching ~40 existing routers — it just changed what those three functions consider "yours".
- **One-line deploy: `git push`.** A cron-poll on the production VPS pulls `master` every 60s, runs Alembic migrations, restarts uvicorn. End-to-end deploy in ~60s. Smoke test (`scripts/smoke_test.py`) hits 26 critical endpoints after each deploy.
- **Telegram Mini App auth = `initData` HMAC validation** bridged to the web session cookie. Mini App and web share the exact same auth layer; no separate API token plumbing.
- **HMAC-signed Telegram Stars invoice payloads** prevent URL tampering (you can't change the product to "pro_forever" after `createInvoiceLink`). Idempotent payment application via `UNIQUE` constraint on `telegram_payment_charge_id` — re-delivered webhooks are silent no-ops.
- **Experimental features are opt-in per user**: graph view, habits tracker, mood log, time tracking, achievements, custom templates, school-portal sync. Off by default; switched on from settings. Bundled into named presets ("Школьник", "Студент", "Максимум").

---

## Stats (snapshot)

| Metric | Value |
|---|---|
| First commit | 2026-05-02 |
| Total commits | 511 |
| Python LoC (app/) | ~20,000 |
| Tests | 850+ |
| Alembic migrations | 39 |
| Per-feature modules | 33 |
| Tests pass on CI | ✅ |
| Production smoke endpoints | 26/26 ✅ |

---

## Built with Claude Code (and yes, I want to talk about it)

This project was written in pair with [Claude Code](https://claude.com/claude-code) — an AI coding assistant. I'm not going to pretend otherwise. What I *will* say:

- **Architecture decisions are mine.** Tier system, payment model, sharing semantics, sidebar layout, feature presets — picked by me. Claude was a fast typist with a good memory of the codebase.
- **Every commit was code-reviewed before push.** Lines I didn't understand got rewritten by hand until I could explain them out loud.
- **Quality bar is enforced by tools, not vibes.** `mypy --strict` + `ruff` + the test suite catch most slop. CI gates every push. The reason this codebase doesn't smell like "AI slop" is that the rails are tight: type errors fail the build, every behavior change ships with a test, and template lint catches bad Alpine.js patterns Claude tends to slip in.
- **I learned a lot.** Writing FastAPI services in pair with an LLM that explains *why* it chose a pattern is the fastest way I've found to absorb production-grade Python. SQLAlchemy 2.0 async, Pydantic v2 validation, HTMX swap strategies — I now know them well enough to debug without help.

Whether that counts as "real" coding depends on your definition. I think it does.

---

## Tech stack

| Layer | Choice |
|---|---|
| **Backend** | FastAPI 0.115 · SQLAlchemy 2.0 (async) · Pydantic v2 |
| **Database** | PostgreSQL 16 · asyncpg · Alembic migrations |
| **Templates** | Jinja2 (server-side rendering everywhere) |
| **Interactivity** | HTMX 2 · Alpine.js (no virtual DOM) |
| **Styles** | Tailwind CSS via CDN (no build step) |
| **Telegram** | python-telegram-bot v21 · WebApp SDK · Stars payments (XTR) |
| **Email** | aiosmtplib · Jinja2 email templates |
| **Auth** | argon2-cffi · itsdangerous (signed session cookie) |
| **Observability** | structlog (JSON) · Sentry · Yandex Metrika |
| **Dev tools** | uv · ruff · mypy `--strict` · pre-commit · pytest-asyncio |
| **CI/CD** | GitHub Actions · cron-poll deploy on prod VPS |

---

## Quick start (local dev)

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Python 3.12+, PostgreSQL 14+.

```bash
git clone https://github.com/SwairIt/doday.git
cd doday
cp .env.example .env
# Edit .env:
#   APP_SECRET_KEY  → python -c "import secrets; print(secrets.token_urlsafe(48))"
#   DATABASE_URL    → postgresql+asyncpg://user:pass@localhost:5432/doday
#   TEST_DATABASE_URL → ...separate test DB, gets truncated between functions

createdb doday
createdb doday_test
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000` → register → check terminal for verification email (or set `BETA_FREE_FOR_ALL=true` to skip).

**Optional — debug SMTP for verification emails:**

```bash
uv run python -m aiosmtpd -n -l localhost:1025
```

**Optional — Telegram bot worker** (separate process, not under uvicorn):

```bash
# In a second terminal, with TELEGRAM_BOT_TOKEN set in .env:
uv run python -m app.telegram.bot
```

---

## Architecture

```
app/
├── auth/             registration, login, sessions, email verify, soft-verify
├── tasks/            CRUD, recurrence, subtasks, completion, bulk ops
├── projects/         projects + sections + sharing (members + invitations)
├── comments/         markdown comments on tasks
├── labels/           per-task labels with colors
├── pomodoro/         persistent Pomodoro timer (sessions in DB)
├── reminders/        per-task scheduled reminders (cron-driven)
├── stats/            daily-streak + per-priority + per-project stats
├── miniapp/          Telegram Mini App router + initData HMAC + assets
├── telegram/         bot worker (long-polling) + commands + JobQueue
├── billing/          tiers, products catalog, Telegram Stars (XTR) payments
├── experiments/      opt-in feature flags + named presets
├── school/           Russian school-portal sync (МЭШ / Школьный портал МО)
├── links/            task↔task links + graph view (experimental)
├── habits/           daily habit tracker (experimental)
├── mood/             mood log widget (experimental)
├── time_tracking/    per-task time entries (experimental)
├── achievements/     XP + badges (experimental)
├── user_templates/   save-project-as-template (experimental)
├── calendar_feed/    public .ics calendar feed (experimental)
├── views/            HTMX page handlers — the bulk of the web UI
├── pages/            static pages (landing, privacy, terms, pricing, SEO landings)
├── digest/           daily email digest (cron-triggered)
├── help/             help-center articles
├── admin/            admin-only routes (users.is_admin)
├── backup/           JSON/CSV user-data export + import
├── profile/          settings endpoints + share-link
├── sections/         sections within projects
└── templates/        Jinja2 (web + miniapp + email)

alembic/versions/     39 migrations
tests/                pytest, mode=auto, TRUNCATE between functions
docs/superpowers/     design specs + implementation plans (kept in repo)
scripts/smoke_test.py 26-endpoint smoke test against prod
```

---

## Quality bar

Every commit must pass (enforced by `pre-commit` and CI):

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy --strict app/ scripts/
uv run python scripts/lint_templates.py
uv run pytest -q
```

`pre-commit install` wires the first four into a git hook. Migrations are forward-only — destructive ones (drop table / drop column) raise `NotImplementedError` on `downgrade()`. Restore from a pre-cleanup tag + `pg_dump` if needed.

---

## Deployment

A cron job runs `deploy-poll.sh` every minute on the production VPS:

1. `git fetch origin master`
2. If `HEAD != origin/master`: `git reset --hard origin/master`, `alembic upgrade head`, kill uvicorn on `:8000`, restart with `--reload`.
3. Smoke test (`scripts/smoke_test.py`) hits 26 endpoints and confirms expected `200`/`303`/`401`. Telegram message on failure.

End-to-end: `git push` → live in ~60 seconds.

---

## Sibling projects on the same infra

Doday is becoming a monorepo for several small vertical products from the same author. They share the FastAPI host, the cron-poll deploy, the PostgreSQL instance, and the `@DodayTaskBot`. Each lives under a path on `getdoday.ru`:

- **[`/lessio`](https://getdoday.ru/lessio)** — Telegram-native booking + payments for tutors and online coaches. Validation phase opened 2026-05-25; if waitlist reaches 100 by 2026-06-01 → MVP. Code: [`app/lessio/`](app/lessio/), tables prefixed `lessio_*`, Stars products `tutor_pro_*` in [`app/billing/products.py`](app/billing/products.py).
- **[`/game`](https://getdoday.ru/game)** — Беллстрой ТВ, infinite arcade with Italian-brainrot enemies. Procedural Three.js, no build step. Code in [`app/static/game/`](app/static/game/).
- **[`/taptower`](https://getdoday.ru/taptower)** — Tap Tower Mini App game (proxied legacy module).

The pattern: a new vertical lives as `app/<vertical>/` with its own router, models (prefixed table names), templates, and tests. Migrations append, never alter Doday's `public` schema. Shared infra (auth, billing, Mini App framework) is pulled in via imports — no duplication. When a vertical proves itself out (≥1K MRR or strategic), it gets extracted into its own repo.

---

## Roadmap (next 3 months)

See [getdoday.ru/roadmap](https://getdoday.ru/roadmap) for the live version. Highlights:

- **Now (May–Jun):** Telegram Stars payments live ✅, public team invite links, mobile app polish.
- **Next (Jun–Jul):** Parent dashboard (Family tier), iCal calendar feed v2, public API + Personal Access Tokens.
- **Maybe (Q3):** Native iOS app (via Capacitor wrapping the Mini App), Russian language English-natural quickadd parser, voice-input via Telegram.

---

## Contributing

PRs welcome. Before submitting:

- Run the full quality bar above.
- Add tests for any new behavior — service-layer tests over endpoint tests where possible.
- Follow the per-feature folder pattern: `app/<feature>/{router,service,models,schemas}.py`.
- Keep touched files focused — splitting a 600+ LoC file is fair game.
- Commit messages in Russian past-tense match the existing log style (single Russian-speaking maintainer), but English is fine for PRs.

Open an issue first for anything bigger than a bugfix — happy to discuss scope.

---

## Author

[@SwairIt](https://github.com/SwairIt) · 15 · solo dev · pair-programs with Claude Code · always curious.

Reach me: [doday.support@gmail.com](mailto:doday.support@gmail.com)

---

## License

MIT — see [LICENSE](LICENSE).

---

<sub>If this repo is useful to you, a ⭐ is appreciated.
If you spot a bug, file an issue — I read every one.
If you want to use the code commercially, MIT lets you; if you also want to sponsor the project, that's <a href="https://getdoday.ru/pricing">pricing</a>.</sub>
