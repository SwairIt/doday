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
| C15 | Inline edit (pencil) + delete + Esc-cancel | ✅ done | `27593e1`, `b70b09f` |
| C16 | Search palette ⌘K (Alpine + ILIKE через func.lower) | ✅ done | `b70b09f` |
| C17 | Profile + статистика + удаление аккаунта (cascade) | ✅ done | `227be87` |
| C18 | Mobile polish (drawer + FAB) | ✅ done | `44ed1af`, `b70b09f` |
| C19 | Tests for new features green | ✅ done (128 PASSED) | n/a |
| C20 | README + final PROGRESS + duration | ✅ done | `80a7aa1`, этот коммит |

**Test count: 128 passing.**

**Тестовый аккаунт (создан 2026-05-03):**
- Email: `yarik@doday.app`
- Password: `ChangeMe1234!` (смени сразу через /app/profile или DB)
- Email подтверждён, Inbox + 3 sample-задачи провижены

## Loop session totals

- **Первый коммит** (C0): `3459918` — `2026-05-03 01:07:07 +0300`
- **Последний коммит** (C16+C18 финал): `b70b09f` — `2026-05-03 07:33:49 +0300`
- **Длительность работы**: **6 часов 27 минут** непрерывной автономной работы
- **Всего коммитов в master**: 26 за эту сессию
- **Push'ей в origin/master**: каждый чанк (~26)

## Что осталось на следующие итерации

- **Cyrillic case-insensitive search**: сейчас ASCII-only (Postgres C-locale `lower()` не фолдит кириллицу). Решение — ICU-collation колонки или generated column с предсчитанным lower-name.
- **Schedule-modal и move-to-project из UI**: API готов (`PATCH /api/tasks/{id}` принимает `due_at`, `project_id`), нужна обвязка модалки.
- **Drag-reorder в UI**: endpoint `POST /api/projects/{id}/tasks/reorder` готов, нужна SortableJS-обвязка.
- **Реальный SMTP в проде**: код готов (`SMTP_*` env vars + `smtp_start_tls` toggle). Нужен Resend/Brevo API key в `.env` — без кода.
- **Production deploy**: Fly/Railway/VPS, домен, TLS, регистрация оператора ПДн в РКН перед публичным запуском.

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

### 2026-05-04 — session 4 (audience-aware features overnight)

Goal: differentiate UX by audience (school / company / personal) and lay
groundwork for the school-portal integration the user asked about.

| Batch | Что | Commit |
|---|---|---|
| B1 | Audience-селектор при регистрации (3-card picker, миграция 0011, тесты) | `2107f5d` |
| B2 | Welcome-flow per audience — стартовые задачи разные для школы/работы/жизни | `6523086` |
| B3 | Scaffold интеграций со школьными порталами (Школьный портал МО + МЭШ): модель, API, UI в /profile, help-статья, миграция 0012 | `ab46bfc` |
| B4 | Расписание уроков: модель, миграция 0013, страница /app/schedule с кликабельной сеткой Пн-Сб × 8 | `3136820` |
| B5 | Standup-виджет на /today для company-аудитории + расписание-виджет для school | `32aa9cd` |
| B6 | Смена audience в /profile + бейдж режима в сайдбаре | `530d2d2` |
| B7 | Чипы предметов над quickadd для school-аудитории | `498e420` |
| B8 | 🔥-чип серии в шапке (текущая серия + рекорд через `/api/stats/streak`) | `6202713` |
| B9 | Общая ical-подписка `/api/calendar/all.ics` + блок «Календарь-подписка» в /profile | `d29acf0` |
| B10 | Утренний брифинг на /today (4-11 ч., советы под аудиторию) | `36d805c` |
| B11 | Заметка дня внизу /today (per-day localStorage) | `dcfe32e` |
| B12 | Пустые состояния /today под аудиторию + апдейт CLAUDE.md | `79e8309` |
| B13 | Фикс конфтеста: сброс auth-rate-limit между тестами + горячая клавиша «g r» | `38c35f6`, `df6690f` |
| B14 | Help-статья о подписке календаря Apple/Google | `f0d641a` |

**Финальный прогон тестов: 424 passed (~9 мин), 0 failed, 0 errors.**

Новые модели в БД: `users.audience` (0011), `school_integrations` (0012), `schedule_slots` (0013).
Новые модули: `app/school/` (integrations + schedule + subjects), `app/company/` (standup),
`app/calendar_feed/` (.ics feed), `app/stats/router.py` (streak chip endpoint).
Новые экраны и виджеты: `/app/schedule` (сетка уроков), morning_briefing,
standup_widget, today_schedule, daily_note, audience-aware пустые состояния,
🔥-чип серии в шапке, audience-бейдж в сайдбаре.

### 2026-05-04 (продолжение) — батч QoL

После запроса «придумай ещё фишек» — записан брейншторм с ~80 идеями
(`docs/ideas-2026-05-04.md`) и реализованы первые 7 пунктов:

| Батч | Что | Commit |
|---|---|---|
| U2 | Bulk-paste в quickadd: paste нескольких строк → модалка превью → создание списком (POST `/api/tasks/bulk`) | `9d01757` |
| U4 | «Завершено сегодня» — сворачиваемая секция внизу /today (`list_completed_today`) | `49bc0fc` |
| U5 | Auto-save черновика quickadd в localStorage | `634ba38` |
| U6 | Countdown-пины на /today (до 3 одновременно, дата + ярлык, localStorage) | `486f812` |
| U7 | PWA — manifest.webmanifest + service-worker.js + meta в base.html | `33a9d13` |
| U8 | Undo-toast 10с после удаления задачи (восстанавливает по «Отменить») | `7c4a3ce` |
| S1 | Для школы — переключатель «По предметам» на /today (детектит предмет в названии) | `17b482b`, `a8c0d32` |

(U1 sub-task progress bar и U3 markdown в description обнаружены уже реализованными.)

**Финальный прогон тестов после QoL-батча: 444 passed (~8 мин), 0 failed, 0 errors.**

### 2026-05-04 (продолжение 2) — батч глубокой автономки

После «доделай это всё до конца» — реализованы оставшиеся приоритетные пункты
из бэклога:

| Батч | Что | Commit |
|---|---|---|
| I1 | Per-user долгоживущий ical-токен `/api/calendar/feed/<token>.ics`, рассечка `rotate`, миграция 0014 | `711b881` |
| P1-P5 | Парсер quickadd: «срочно/важно», «через 2 часа/30 минут», «к выходным», «вечером/утром/после обеда», «каждый день/неделю/понедельник» → recurrence | `d9fa323` |
| C1 | Sprint countdown widget на /today для company (день N из M, прогресс-бар, дата старта/конца, цель) | `7dd0f05` |
| L3 | Habit-tracker: модель + миграция 0015, `/app/habits` экран, чек-ин по дате, streak-счётчик, 30-дневная сетка, эмодзи-/цвет-палитра | `2e7e128` |
| C2 | Пятничный retro-промпт (Fr-Sun) для company: 3 поля + история по неделям + копирование в markdown | `3f29c6b` |
| S2 | Школьная серия `/api/stats/school-streak` — отдельный streak только по задачам с предметом | `9fa4d4c` |
| S5 | Российские школьные каникулы 2024-2027 в коде, `/api/school/holiday`, баннер «Каникулы! Осталось N дней» / «До каникул N дней» | `bae22d8`, `42343a4` |
| FX | Пин TZ='UTC' на каждое asyncpg-соединение — устраняет off-by-one в `func.date(timestamptz)` ночью локального TZ | `633a37d` |

Новые модели: `users.ical_token` (0014), `habits` + `habit_checkins` (0015).
Новые модули: `app/habits/`, `app/school/holidays.py`.
Новые экраны: `/app/habits` с эмодзи-чекбоксами и сеткой 30 дней.
Новые виджеты на /today: sprint, retro, school_streak, school_holiday.

**Финальный прогон тестов после ночной автономки: 497 passed (~11.5 мин), 0 failed.**

Найденный и пофикшенный баг: streak-эндпоинты возвращали 0 в первые часы
московских суток — Postgres-сессия исполняла `func.date()` в локальном TZ,
а Python-«сегодня» считалось в UTC, даты не совпадали. Теперь все
asyncpg-соединения принудительно UTC (через `connect_args.server_settings`).

Весь backlog с ~80 идеями (universal QoL, парсер дат, рекуррентность, school,
company, personal, геймификация, инфра) лежит в `docs/ideas-2026-05-04.md`
с пометками ✅/🔨/💡 для приоритизации следующих сессий.

### 2026-05-05 — батч «доделай всё до конца» 

После запроса «продолжи, доделай всё до конца» — реализованы оставшиеся
крупные пункты бэклога:

| Батч | Что | Commit |
|---|---|---|
| CSV | `/api/tasks/export.csv` (все/активные) с BOM для Excel + кнопка в /профиле | `050a47d` |
| PIN | Закрепить задачу наверх (миграция 0016 `pinned_at`, кнопка-pin, 📌-бейдж в строке) | `2c6dc3b` |
| TRASH | Корзина с soft-delete (миграция 0017 `deleted_at`), `/app/trash`, восстановление до 30 дней + auto-purge | `cf399da` |
| TIME | Time tracking — start/stop таймер на задаче (миграция 0018 `time_entries`), `/api/time` | `1509121` |
| MOOD | Mood tracker для personal — 1-5 emoji + заметка + 30-дневная цветная полоса (миграция 0019) | `41a94a9` |
| ACH | Достижения — 18 бейджей, производных от данных (без новой таблицы), секция в /профиле | `b451101` |
| WP | Week-plan widget на пн-вт — 3 главные цели на неделю + прогресс-бар (localStorage) | `b0c8eb2` |
| FX | Подгон тестов под soft-delete (delete_task теперь идемпотентный, не raise при повторе) | `abbd519` |

Новые модули: `app/time_tracking/`, `app/mood/`, `app/achievements/`.
Новые миграции: 0016 (pinned_at), 0017 (deleted_at), 0018 (time_entries), 0019 (mood_entries).
Новый экран: `/app/trash` (восстановление + permanent delete).
Новые виджеты на /today: week_plan, mood_widget.
Новая секция в /профиле: «Достижения» с 18 бейджами.

**Финальный прогон тестов после batch «доделай всё до конца»: 538 passed (~14 мин), 0 failed.**

Все 19 миграций применены, ruff strict + mypy --strict зелёные на 207 файлах.
