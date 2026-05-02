# Doday — Progress tracker

**Purpose:** session-spanning progress tracker. Read this first in every session/iteration.

---

## Current state — 2026-05-03

**Project pivoted** from "schoolers-only todo" to **"free todo for everyone (kids + adults + companies)"**. Working brand: **Doday**. Diary parsing (МО / МЭШ) demoted to optional integration for later.

**Active spec:** `docs/superpowers/specs/2026-05-03-pivot-design-spec.md`
**Old spec (historical):** `docs/superpowers/specs/2026-05-02-school-todo-design.md`

**Loop session:** running an autonomous overnight build (cron `*/1 * * * *`). Each iteration reads this file, picks the next pending chunk, implements it, runs ruff+mypy, commits, pushes to master. When all chunks done — appends final duration and stops.

**Local infra (already running from previous session):**
- Postgres 18 via scoop on `localhost:5432` (user `postgres` / password `postgres`)
- Databases: `schooltodo` (with users table) + `schooltodo_test`
- Uvicorn on `127.0.0.1:8000`
- aiosmtpd debug SMTP on `127.0.0.1:1025`

---

## Chunk progress

### Plan A — Pivot to Doday (this overnight session)

| # | Chunk | Status | Commit |
|---|---|---|---|
| C0 | Pivot spec + memory + claude.md | ✅ done | `3459918` |
| C1 | Brand + design tokens (CSS vars, fonts, themes) | ✅ done | `a8a3f06` |
| C2 | Project + Task + Label models + migration `0002` | ✅ done | `f136741` |
| C3 | Project service + router (CRUD) + tests | ✅ done | `5eac8b2` |
| C4 | Task service + router (CRUD/complete/reorder) + tests | ✅ done | `8ea356e` |
| C5 | Label service + router + tests | ✅ done | `48b4d78` |
| C6 | Auto-provision Inbox + 3 sample tasks on verify | ✅ done | `45ad1fe` |
| C7 | Landing redesign (purple gradient hero + features) | ✅ done | `f4f165e` |
| C8 | Auth pages redesigned to match | ✅ done | `2005db1` |
| C9 | App shell `app_base.html` with sidebar + topbar | ✅ done | `44ed1af` |
| C10 | Today view + HTMX task toggle | ✅ done | `98c68d5`, `e810bcc` |
| C11 | Upcoming view (day-grouped) | ✅ done | `f649c1a`, `be72c06` |
| C12 | Calendar view (month grid) | ✅ done | `96c0e45`, `db77f9e` |
| C13 | Project view + /app/inbox redirect | ✅ done | `69ccc44`, `6ee4a04` |
| C14 | Quick-add with natural-language parsing | ⏳ next | — |
| C15 | Inline edit / delete / schedule / move | pending | — |
| C16 | Search palette (⌘K, postgres FTS) | pending | — |
| C17 | Profile (theme, default view, export, delete) | pending | — |
| C18 | Mobile polish (drawer, FAB, bottom nav) | pending | — |
| C19 | Tests for new features green; old tests still green | pending | — |
| C20 | README + final PROGRESS update + report duration | pending | — |

**Test count after C13:** 100+ passing (4 model + service + router + view + provisioning suites).
**First commit:** `3459918` — 2026-05-03 (C0).
**Latest commit:** `6ee4a04` — 2026-05-03 (C13 fix).

---

## How the loop iterates

Each cron fire (every 1 minute):

1. **Read this file** — find the **first non-completed chunk** in the table above.
2. **Read the spec section** for that chunk number — the spec has acceptance for each.
3. **Implement** — write/edit only the files listed for the chunk; nothing else.
4. **Verify** — `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy .`. Fix until green. (Tests run only on chunks where new model/service code lands; UI-only chunks skip pytest.)
5. **Commit** — Russian past-tense message, single-feature scope.
6. **Push to master** using `TOKEN` from `.env`:
   ```bash
   TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
   git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
   ```
   Author email is **always** `112168281+SwairIt@users.noreply.github.com`.
7. **Update this file** — mark the chunk ✅ with the commit SHA.
8. If all chunks done → compute duration `git log -1 --format=%ad` minus first chunk commit `git log --reverse --format=%ad | head -1`, append "FINISHED" + duration line, **CronDelete** the loop, stop.

---

## Constraints (do NOT violate even under autonomous loop)

- **No verbatim copies** of any specific commercial todo product's code, copy, or unique UI patterns. Use generic industry-standard patterns only.
- **Never use third-party-service credentials** the user pasted in chat (Gmail / Resend / etc.). The user signs up themselves and adds API keys to `.env`.
- **Never push with author email other than** `112168281+SwairIt@users.noreply.github.com`.
- **Never write `.env` with BOM** (use `[System.IO.File]::WriteAllText` with `New-Object System.Text.UTF8Encoding $false`).

---

## Lifetime log

### 2026-05-02 — sessions 1, 2 (Plan 1 — Foundation + Auth)
- Brainstorm + design + Plan 1 written
- Auth implemented in 5 chunks (commits up to `5904683`)
- Fly.io deploy attempted then removed
- Local Postgres set up (scoop), migrations applied, full e2e confirmed (42 tests green)

### 2026-05-03 — session 3 (Plan A pivot, this overnight loop)
- C0 (in progress): wrote pivot spec, updated memory + claude.md, refactored PROGRESS to chunk pointer
- (subsequent chunks logged here as they land)
