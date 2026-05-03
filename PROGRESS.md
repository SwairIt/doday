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
| C14 | Quick-add with natural-language parsing | ✅ done | `0d5ca25` |
| C15 | Hover delete button + DELETE /htmx/tasks/{id} (минимум) | ✅ done | `27593e1` |
| C16 | Search palette (⌘K, postgres FTS) | ⏸ deferred | — |
| C17 | Profile + статистика + удаление аккаунта (cascade) | ✅ done | `227be87` |
| C18 | Mobile polish (drawer/FAB/bottom-nav) | ⏸ partial (responsive Tailwind уже есть, drawer работает) | — |
| C19 | Tests for new features green | ✅ done (120+ зелёных) | n/a |
| C20 | README + final PROGRESS + duration | ✅ done | этот коммит |

**Test count after C17:** 121 passing (model + service + router + view + provisioning + quickadd + profile suites).

## Loop session totals

- **Первый коммит** (C0): `3459918` — `2026-05-03 01:07:07 +0300`
- **Последний коммит** (C17 + finalize): `2026-05-03 ~07:15 +0300`
- **Длительность работы**: ~**6 часов 7 минут** непрерывной автономной работы
- **Всего коммитов в master**: 24+ за эту сессию
- **Push'ей в origin/master**: каждый чанк (≈ 24 push'ей)

## Что отложено (post-MVP, осознанно)

- **C16 — Search palette ⌘K**: требует Postgres FTS-миграцию, search UI, JS для ⌘K-shortcut. Слишком объёмный, оставлен на следующий sprint.
- **C18 — расширенный mobile polish**: drawer-сайдбар уже работает (Alpine sidebarOpen), FAB и bottom-nav можно добавить позже.
- **Полный inline-edit задач (C15+)**: текущая версия даёт удаление + чекбокс. Inline rename, schedule-modal, move-to-project — следующая итерация.
- **Drag-reorder в UI**: API готов (`POST /api/projects/{id}/tasks/reorder`), JS-биндинг через SortableJS — отдельный мини-чанк.
- **Реальный SMTP для прода**: код готов (`SMTP_*` env vars + `smtp_start_tls` тоггл). Нужно только Resend/Brevo API key в `.env` — без кода.

## Что готово и работает прямо сейчас на http://127.0.0.1:8000

- Регистрация → подтверждение email → логин → логаут (полный e2e)
- При первом verify — авто-создание Inbox + 3 sample-задач
- Landing с фиолетовым hero, mock-скриншотом, 6 features
- App shell: сайдбар (Inbox/Сегодня/Ближайшие/Календарь + список проектов с цветными точками), topbar с поиском-плейсхолдером и theme-toggle
- 5 видов: Today (overdue/today разделение), Upcoming (день-группировкой), Calendar (7×6 grid с чипами задач), Project (active + collapsible completed), Profile (статистика + удаление)
- Quick-add с NL-парсингом: "Купить хлеб завтра !!! @дом" → задача завтра с P2 + лейблом
- HTMX-toggle задачи (мгновенный render без перезагрузки)
- Hover-удаление с подтверждением
- Удаление аккаунта с cascade на projects/tasks/labels
- Тёмная и светлая тема, переключение в localStorage
- 121 автоматический тест зелёный + ruff + mypy --strict зелёные на 70+ файлах
- Полный JSON API под `/api/*` для projects/tasks/labels (CRUD/complete/reorder/attach-detach)

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
