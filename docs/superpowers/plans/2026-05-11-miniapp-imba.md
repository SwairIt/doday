# Mini App — «имба» mode

**Дата:** 2026-05-11
**Контекст:** v2 (parity + stats + polish) закрыт, но Mini App ощущается
как middle-tier todo-апп. Цель этой работы — сделать **best-in-class
Telegram Mini App** среди todo-аппов. Пользователь дал карт-бланш на
все 8 фаз, ~25-30 часов работы, без loop'а — итерации по «продолжи».

**Бизнес-решения юзера:**
- Все 8 фаз делаем
- Анимации **CSS-only + минимум JS** (не подключаем motion.dev/anime.js —
  меньше bundle, быстрее в TG-WebView)
- Pomodoro храним **в БД** (новая таблица `pomodoro_sessions`) — даёт
  cross-device + «сколько часов на задачу всего»

## Архитектурные принципы

1. **Backwards-compat:** не ломаем v1/v2 API. Только дополняем.
2. **DB-migrations через Alembic** (2-3 новые миграции: pomodoro,
   reminders, user_progress)
3. **Tests-first где разумно** — каждый новый endpoint покрыт ≥1 test'ом
4. **Каждый чанк — отдельный коммит** с Russian past-tense
5. **Архитектуру не ломаем** — `/miniapp/*` остаётся изолированным
   модулем; `/app/*` веба не трогаем

---

## Фаза α — Личность и анимационный фундамент (4-5ч, 5 чанков)

### A1 — Time-aware greeting hero на Today
- Утро (5-11): «🌅 Доброе утро, {email_local}»
- День (11-17): «☀️ Добрый день, …»
- Вечер (17-23): «🌆 Добрый вечер, …»
- Ночь (23-5): «🌙 Спокойной ночи, …»
- Подзаголовок зависит от состояния: «{N} задач на сегодня» / «всё закрыто, отдыхай» / «нет планов — добавь первую»
- Имя берётся из email-local-part (до @) или из user.first_name (если есть)
- Helper в router: `_greeting_for(user, now, tasks_count)`
- **Файлы:** `app/miniapp/router.py`, `app/templates/miniapp/today.html`

### A2 — Spring animations baseline
- В `_base.html` глобальный `cubic-bezier(0.34, 1.56, 0.64, 1)` для всех `.task-card`, `.swipe-content`, button-press, sheet-open
- Active states получают spring-scale (95% → 100% с overshoot)
- **Файлы:** `_base.html` CSS

### A3 — Confetti micro-burst на каждое complete
- Текущий confetti firing только на 100%-empty
- Добавить: при каждом complete (tap-checkbox / swipe-left) — выстрел 5-8 частиц из точки чекбокса с физикой (gravity)
- Color = priority class цвет (P1=rose, P2=amber, P3=sky, P4=violet)
- Не firing если confetti library не загрузилась (graceful)
- **Файлы:** `app/miniapp/static.py` (JS)

### A4 — Smooth complete-animation
- Tap чекбокс → 200ms pulse (border-color → grad-bg, scale 1.0→1.3→1.0)
- Title text получает strike-through через CSS `width 0→100%` transition (псевдоэлемент)
- Row collapses через `max-height` transition (current — removeNode delay 300ms, заменить на elegant collapse-fade)
- **Файлы:** `app/miniapp/static.py`, `_base.html`, `task_card.html` (data-state хук)

### A5 — Animated empty-states + hero-blob drift
- Empty-state SVG получают `@keyframes` (солнышко в `empty_today.html` slow-rotate, коробка в `empty_inbox.html` slow-bounce)
- `.hero-blob` получает `@keyframes float-drift` slow position-shift
- **Файлы:** все `_partials/empty_*.html`, `_base.html`

---

## Фаза β — Gestures (3-4ч, 4 чанка)

### B1 — Long-press action-sheet (iOS-style)
- На task-card long-press (touchstart + 500ms hold) → vibrate haptic medium + появляется bottom-sheet с быстрыми действиями
- Действия: «Сегодня / Завтра / +неделя / +месяц / Без даты / Изменить P1-P4 / Дублировать / 🗑 Удалить»
- Каждое — PATCH/POST на бэк через existing endpoints
- **Файлы:** `static.py`, новый `_partials/quick_actions_sheet.html`

### B2 — Bulk select mode
- Long-press на пустой части list-секции (или toggle-кнопка в header) → mode active, чекбоксы становятся multi-select
- MainButton показывает «Завершить N / Удалить N / Отменить»
- Tap-on-task переключает выделение, не открывает sheet
- Action на batch: POST /miniapp/api/tasks/bulk {ids[], action}
- **Файлы:** `static.py`, новый endpoint в `router.py`

### B3 — Drag-to-reorder
- На каждой task-card touch-handle (3 точки слева) — захват drag
- Within current secion: pointermove → reorder live
- Drop → POST /miniapp/api/tasks/reorder {ids[]}
- **Файлы:** `static.py`, новый endpoint

### B4 — Customizable swipe-actions через Settings
- В Me-page → секция «Настройки» — toggle «Свайп влево = X», «Свайп вправо = Y»
- Опции: complete / snooze / delete / edit
- Сохраняем в `user_settings` (новое JSON-поле на user или отдельная таблица)
- **Файлы:** migration, model, router, me.html, static.js

---

## Фаза γ — Gamification (3ч, 5 чанков)

### G1 — XP system: миграция + service
- Migration `0024_user_progress.py` — таблица `user_progress` (user_id PK, xp_total int, level int, last_level_up_at)
- Service `app/gamification/service.py`:
  - `award_xp(session, user_id, amount, reason)` — добавляет XP, считает level (100 XP per level), записывает level-up event
  - `level_for_xp(xp) -> int` (1 + xp // 100)
- Hook в complete_task — каждое завершение даёт XP (P1=10/P2=5/P3=3/P4=2)
- **Файлы:** migration, gamification/service.py, hook в tasks/service complete

### G2 — Level display + level-up celebration
- В Me-page: hero-block получает level-circle с XP-progress-ring
- При level-up → full-screen modal с конфетти + emoji-rank + кнопка «Окей»
- Level-up event возвращается из complete-endpoint (если случился) — клиент triggerит celebration
- **Файлы:** me.html, static.py, router

### G3 — Achievements (~15)
- Migration `0025_achievements.py` — таблица `user_achievements` (user_id, achievement_key, unlocked_at)
- Yaml/Python-список 15 achievements с criteria-функциями
- При complete/login проверяем unlocked → INSERT
- Display в Me-page: горизонтальный grid с эмодзи + tooltip
- Unlock event тоже triggerит celebration
- **Файлы:** migration, gamification/achievements.py, me.html

### G4 — Daily challenge
- Random pick per day (deterministic на user_id + date): «закрой 5» / «закрой 1 P1» / «не пропусти просрочку»
- Шторм в Today-header: «Сегодняшний вызов: …»
- При выполнении → +20 XP + ачивка
- **Файлы:** gamification/daily.py, today router, today.html

### G5 — Streak fire-icon scaling
- Текущий 🔥 — статичный emoji
- Replace на SVG fire-icon, size scales with streak (1d=24px, 7d=36px, 30d=48px, 100+=56px с glow-effect)
- **Файлы:** me.html (inline SVG)

---

## Фаза δ — Pomodoro (4ч, 5 чанков)

### P1 — DB + service
- Migration `0026_pomodoro_sessions.py` — `pomodoro_sessions` (id, user_id, task_id NULL, started_at, ended_at, duration_min, kind: 'focus'|'break-short'|'break-long', completed bool)
- Service: `start(user_id, task_id, kind)`, `stop(session_id)`, `list_active(user_id)`, `time_on_task(task_id) -> minutes`
- **Файлы:** migration, app/pomodoro/

### P2 — Pomodoro button + endpoints
- POST `/miniapp/api/pomodoro/start` body `{task_id?, kind}`, returns `{session_id, started_at, duration_min}`
- POST `/miniapp/api/pomodoro/stop/{id}` body `{completed: bool}`
- GET `/miniapp/api/pomodoro/active` returns active session or null
- В task_card: иконка-таймер справа от title (между title и chips), tap → start
- В task_sheet: показывать `time_on_task` если есть accumulated time
- **Файлы:** router.py, task_card.html, task_sheet.html

### P3 — Mini floating timer widget
- Когда pomodoro active — фиксированная карточка снизу (выше bottom-nav) с countdown + task-title (если есть) + кнопка стоп
- Persist через page reload (запрос /pomodoro/active при mount)
- Tap на mini → open full-screen mode
- **Файлы:** `_partials/pomodoro_widget.html`, static.js, _base.html include

### P4 — Full-screen pomodoro mode
- Modal full-screen с большим circle-timer (svg progress)
- Текст: «Сфокусируйся: {task.title}»
- Кнопки: pause / stop early
- Тикающий subtle sound? — нет (пропускаем per юзер-decision)
- **Файлы:** `_partials/pomodoro_fullscreen.html`

### P5 — Break management + time-on-task display
- После окончания focus-session → автоматический break-suggestion (5 мин)
- После 4 focus → long break (15 мин)
- В task_sheet: показ total minutes spent + history-list последних 5 sessions
- **Файлы:** pomodoro service, task_sheet.html, static.js

---

## Фаза ε — Notifications через бот (3ч, 4 чанка)

### N1 — Reminders DB + service
- Migration `0027_reminders.py` — `reminders` (id, user_id, task_id, remind_at, sent_at NULL, kind: 'before-due'|'custom')
- Service create/list/mark_sent
- **Файлы:** migration, app/reminders/

### N2 — Reminder picker в task_sheet
- В sheet секция «🔔 Напомнить»: chips «15 мин / 30 мин / 1 час / Другое»
- «Другое» — datetime picker
- Сохраняется в БД через POST /miniapp/api/tasks/<id>/reminders
- **Файлы:** task_sheet.html, router

### N3 — Cron-worker для approaching reminders
- В `app/telegram/bot.py` (или отдельный worker) — каждую минуту scan: reminders where remind_at <= now AND sent_at IS NULL
- Для каждого — `bot.send_message(chat_id, "🔔 Через ... : Купить молоко", inline_keyboard=[Открыть/Завершить/Отложить 30 мин])`
- Mark sent_at
- **Файлы:** bot.py extension, либо app/reminders/worker.py

### N4 — Morning digest + overdue alerts
- Cron 09:00 — для каждого linked-tg-user шлём «Доброе утро! Сегодня у тебя: 5 задач (3 P1 / 2 P3)»
- Cron 20:00 — для overdue >1 день шлём «У тебя {N} просроченных задач»
- **Файлы:** extension в digest/service.py

---

## Фаза ζ — Sections + Kanban view (3-4ч, 4 чанка)

### K1 — Section endpoints + bottom-sheet
- Web уже имеет sections; mini-app — добавить /miniapp/api/sections
- GET project/<id>/sections, POST, PATCH, DELETE
- Bottom-sheet для CRUD sections (rename / add / reorder)
- **Файлы:** router, new section_sheet.html partial

### K2 — Project view: list ↔ kanban toggle
- В header project.html — toggle «📋 Список» / «📊 Доска»
- View-state хранится в URL ?view=kanban или localStorage
- **Файлы:** project.html

### K3 — Kanban rendering
- Render: каждая section = column, задачи как cards, horizontal-scroll
- Card: compact version task_card (title + чипсы, без description)
- Empty section → «+ задача»
- **Файлы:** new project_kanban.html partial

### K4 — Drag-and-drop задач между sections
- Touch-based drag, drop в другую колонку → PATCH task.section_id
- **Файлы:** static.js

---

## Фаза η — Comments + Notes (3-4ч, 3 чанка)

### C1 — Markdown notes accordion в task_sheet
- В sheet добавить collapsible «📝 Заметки»
- Textarea с markdown-light (bold/italic/links/lists через `**bold**`/`_italic_`/`[txt](url)`/`- list`)
- Server: задача уже имеет `description` поле → используем его
- Render preview через simple-markdown JS lib (или Python markdown server-side)
- **Файлы:** task_sheet.html, static.js (или inline parser)

### C2 — Comments thread accordion
- Comments table уже существует — добавить endpoints для mini-app
- GET /miniapp/api/tasks/<id>/comments, POST {text}
- В sheet — accordion «💬 Комментарии (N)» с list + input-bar
- **Файлы:** router, task_sheet.html, comments service

### C3 — Quick-comment из бота
- В bot.py — `/comment <task-id> <text>` → POST comment
- Опционально reply-on-message: forward задача из mini-app в чат с inline-keyboard «Ответить» → adds comment
- **Файлы:** bot.py

---

## Фаза θ — Visual hits (2-3ч, 5 чанков)

### V1 — Glassmorphism + gradient borders
- Bottom-sheets получают `backdrop-filter: blur(20px)` + `bg-rgba(20,20,30,0.85)` для frosted-glass
- Active priority-chips border = `linear-gradient` через background-clip trick
- **Файлы:** _base.html CSS

### V2 — Custom priority emojis
- Replace «P1/P2/P3» текст на emoji: 🔥 (P1) / ⚡ (P2) / 💧 (P3) / 💨 (P4)
- В task_card chips, task_sheet picker, miniapp.js (quick-actions)
- **Файлы:** task_card.html, task_sheet.html, _partials/*

### V3 — Screenshot/share-mode для streak
- На Me-page — кнопка «Поделиться streak'ом»
- Генерирует beautifu PNG: «Yaroslav · 🔥 7 day streak · 142 tasks closed» на gradient-bg
- Server-side через PIL или client-side через canvas
- Sends to TG-share-sheet через `tg.shareToStory()` или similar
- **Файлы:** new endpoint /miniapp/api/share/streak.png, me.html

### V4 — Accent-color picker
- В Settings: 5 accent-варианта (violet default / rose / emerald / sky / amber)
- Сохраняется в user_preferences
- Перекрашивает `--accent` CSS var через JS на mount
- **Файлы:** user model field или JSON, me.html, static.js

### V5 — Dynamic Island-style toasts
- При тапах (priority changed / project moved / pomodoro started) — top-pill notification 2 sec slide-down
- Replace alerts() с этими
- **Файлы:** static.js new function `dodayToast(msg, kind)`

---

# Loop правила (применимы хоть без cron'а)

- Каждая итерация: смотрим какой следующий незакрытый чанк, делаем 1-2-3
  в зависимости от размера и контекста
- После каждого commit — push в master + auto-deploy через cron-poll
  (~60 сек до прода) + smoke 23/23 GREEN после деплоя
- Russian past-tense commits, author
  `112168281+SwairIt@users.noreply.github.com`
- Pre-commit (ruff/mypy strict/jinja-linter) **green** перед commit'ом
- pytest -q зелёный после каждого чанка
- Когда юзер пишет «продолжи» — продолжаем со следующего чанка
- Архитектуру не ломаем — только дополняем

---

# Прогресс

## Фаза α — Личность + анимации
- [x] A1 — Time-aware greeting hero ✅
- [x] A2 — Spring animations baseline ✅
- [x] A3 — Confetti micro-burst на каждое complete ✅
- [x] A4 — Smooth complete-animation ✅
- [x] A5 — Animated empty-states + blob-drift ✅

## Фаза β — Gestures
- [x] B1 — Long-press action-sheet ✅ `fa09fa3`
- [x] B2 — Bulk select mode ✅ `fa09fa3`
- [x] B3 — Drag-to-reorder ✅
- [x] B4 — Customizable swipe-actions ✅

## Фаза γ — Gamification
- [ ] G1 — XP migration + service
- [ ] G2 — Level display + level-up celebration
- [ ] G3 — Achievements (15+)
- [ ] G4 — Daily challenge
- [ ] G5 — Streak fire-icon scaling

## Фаза δ — Pomodoro
- [ ] P1 — DB + service
- [ ] P2 — Pomodoro button + endpoints
- [ ] P3 — Mini floating widget
- [ ] P4 — Full-screen mode
- [ ] P5 — Break management + time-on-task

## Фаза ε — Notifications
- [ ] N1 — Reminders DB + service
- [ ] N2 — Reminder picker в sheet
- [ ] N3 — Cron-worker для approaching
- [ ] N4 — Morning digest + overdue alerts

## Фаза ζ — Sections + Kanban
- [ ] K1 — Section endpoints + bottom-sheet
- [ ] K2 — Project view toggle
- [ ] K3 — Kanban rendering
- [ ] K4 — Drag-and-drop между sections

## Фаза η — Comments + Notes
- [ ] C1 — Markdown notes
- [ ] C2 — Comments thread
- [ ] C3 — Quick-comment из бота

## Фаза θ — Visual hits
- [ ] V1 — Glassmorphism + gradient borders
- [ ] V2 — Custom priority emojis
- [ ] V3 — Streak share mode
- [ ] V4 — Accent-color picker
- [ ] V5 — Dynamic Island toasts

**Итого:** 35 чанков ≈ 25-30ч.

Финальный commit когда всё ✅: «miniapp: имба-mode завершён»
+ длительность/счётчик в PROGRESS.md.
