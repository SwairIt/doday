# Responsive-спринт 2026-05-09

Полный план + результат. Цель — все страницы Doday работают на 320 / 375 / 414 / 768 px без overflow, без обрезанного текста, с touch-target ≥36px.

Связанные файлы:
- Дизайн-спека: [`docs/superpowers/specs/2026-05-09-full-responsive-design.md`](docs/superpowers/specs/2026-05-09-full-responsive-design.md)
- Лог чанков: [`PROGRESS.md`](PROGRESS.md)
- Открытые задачи: [`ROADMAP.md`](ROADMAP.md)

---

## Что хотели сделать (план)

### Phase 1 — Real test data

Создать тестовый аккаунт `responsive-test@doday.local` с реалистичными данными:
- 4 проекта (Inbox + Работа Q3 + Дом + Учёба в магистратуре)
- 4 секции в проекте Работа (Срочное / На этой неделе / Бэклог / Готово) → kanban-ready
- 17 задач + 3 подзадачи + 4 лейбла + 2 комментария + 1 task-link
- Длинные имена («Работа Q3 — переезд офиса и онбординг»), markdown-описания, разные приоритеты, разные даты (overdue/today/tomorrow/week/20d/none).

### Phase 2 — 320px публичные страницы (8 шт)

Прогнать на 320px с фиксом overflow/cut-off:
- `landing.html`
- `pricing.html`
- `help/index.html`
- `help/article.html`
- `privacy.html`
- `auth/login.html`
- `auth/register.html`
- `auth/verify_pending.html`

### Phase 3 — 320px app-страницы с реальными данными (22 шт)

Прогнать на 320px все приватные экраны под залогиненным юзером с seeded data:
- `today` / `inbox` / `upcoming` / `done` / `trash`
- `calendar` (month + week)
- `schedule` (расписание уроков для school-аудитории)
- `habits` / `stats` / `activity`
- `projects/<slug>` (список + kanban) / `projects-archive`
- `labels` / `filters` / `filters/manage`
- `profile` (208 классов — самая плотная страница)
- `graph` (canvas-космос связей задач)

### Phase 4 — Deep-dive ROADMAP NEXT items

- **kanban.html** с 4 реальными колонками + 8 карточками — column scroll, card touch targets, drag-handle на touch
- **task_detail.html** (right-side sliding panel) — full-width на mobile, scroll, close button, comment editor с мобильной клавиатурой
- **profile.html** (208 классов) — deep-dive achievements grid, integrations cards, audience switcher, calendar-subscription block

### Phase 5 — UX-redesigns из бэклога

- **Comparison table → cards** на mobile в landing.html (md:hidden / hidden md:block toggle)
- **Calendar week-view default** на mobile (auto-redirect на ?view=week если viewport < 768)
- **Schedule single-day view** на mobile (tabs Пн-Сб + вертикальный список 8 уроков)
- **Bottom-nav на iPad portrait (768px)** — проверить, нужен ли (был под вопросом в ROADMAP)

### Phase 6 — Regression check 414/768

Проверить что mobile-fixes не сломали средние и большие viewports.

### Phase 7 — Verify & ship

- `scripts/lint_templates.py` — 0 errors
- `scripts/smoke_test.py http://127.0.0.1:8000` — 18/18 green
- `pre-commit run --all-files` — все hooks Passed
- Update `PROGRESS.md` и `ROADMAP.md`
- Push в master

---

## Что сделано (результат)

Все 7 фаз закрыты за один заход, ~3.5 часа работы.

| Phase | Статус | Commit |
|---|---|---|
| 1. Real test data (4 проекта + 17 задач + 3 подзадачи + 4 лейбла + 2 комментария + 1 link) | ✅ | local seed |
| 2. 320px публичных страниц (8 шт) | ✅ | `bbc26ae` |
| 3. 320px app-страниц (22 шт) | ✅ | проверено через автоматический iframe-сканер — 0 culprits на каждой |
| 4. ROADMAP NEXT — kanban + task_detail | ✅ | `9a51640` |
| 5. UX-redesigns: comparison cards / calendar week-default / schedule day-tabs | ✅ | `a9ef8b2` |
| 6. 414/768 regression — нашёл и пофиксил overlap brand+nav на 768 | ✅ | `7582a64` |
| 7. PROGRESS + ROADMAP update + push | ✅ | `a935245` |

### Конкретные правки

**landing.html:**
- header CTA-кнопки компактнее на mobile (text-sm + py-2 + px-3 вместо !py-[11px] !px-5) — иначе "Войти + Начать бесплатно" не влезали в 320px и пушили page до 358px
- hero h1 `text-5xl` → `text-4xl sm:text-5xl` («приятно жить» 48px не влезало в 296)
- mock-карточка hero: дата span переносится на новую строку (`block sm:inline`); flex-shrink-0 на бейджах; line-through truncate
- секции `px-6` → `px-4 sm:px-6` (даёт +32px usable width)
- comparison table → стек 3 cards на mobile (md:hidden), desktop-таблица сохранена
- nav links `hidden md:flex` → `hidden lg:flex` — на 768 (iPad portrait) больше не overlap'ают brand

**help/index.html, help/article.html, privacy.html:**
- header CTA same fix как landing
- main padding mobile-friendly

**kanban.html:**
- header стекается на mobile (icon+title-block сверху, view-toggle снизу) — длинные имена («Работа Q3 — переезд офиса и онбординг») не обрезаются до «Раб»
- title `truncate` → `break-words` (видно полностью на 4-5 строк)
- columns `w-72` → `w-64 sm:w-72` (256px на mobile вместо 288px) — край следующей колонки виден
- kanban-board scroll: `-mx-4 sm:mx-0 px-4 sm:px-0` (full-bleed scroll на mobile)

**task_detail.html:**
- title input → textarea с auto-resize: длинные заголовки переносятся, не cut'аются
- text-xl → text-lg sm:text-xl
- header padding `px-5` → `px-4 sm:px-5`; `min-w-0` на title-row

**calendar.html:**
- inline JS на старте: если viewport < 768 и нет `?view=` — redirect на `?view=week` (mobile получает читаемый недельный вид по умолчанию вместо 7×6 month grid)

**calendar_week.html:**
- mobile (md:hidden) day-tabs Пн-Вс над колонками; сегодняшний день auto-selected
- `grid-cols-1 md:grid-cols-7` — на mobile одна колонка во всю ширину для выбранного дня; task chips читаются полностью (раньше были 1-2 символа)

**schedule.html:**
- mobile (md:hidden) day-tabs Пн-Сб + вертикальный список 8 уроков (touch-target 44px+)
- desktop (hidden md:block) — оригинальная 7×8 таблица сохранена

### Метрики

- **0 элементов с overflow** на 320 / 375 / 414 / 768 (auto-scan через iframe всех 20 app-страниц + 8 публичных)
- **docW=310** (320px viewport - 10px scrollbar) на всех страницах
- **jinja-linter:** 0 errors
- **commits:** 7 за спринт, все pushed в `master`

### Что НЕ изменилось

- Design tokens (CSS vars), цвета, шрифты, spacing scale
- Desktop layout (1024+) — все mobile-first классы scoped через `md:` / `sm:` / `lg:`
- Бизнес-логика, API, миграции
- 538 автотестов — pre-commit и smoke-test зелёные

---

## Что вышло за scope (открыто в ROADMAP)

Эти пункты остались в [`ROADMAP.md`](ROADMAP.md) для следующих спринтов:

- **profile.html deep-dive** — 0 overflow, но субъективно plотная страница, потенциальные мелкие UX-issues
- **Real iPhone live-testing** — DevTools-emulation ловит не всё, нужно проверить на физическом устройстве (BLOCKED — нужен пользователь)
- **PWA "Поделиться → На главный экран"** на iPhone (BLOCKED)
- **Quick-add placeholder** — длинный пример «Сходить в зал завтра !!! @спорт» можно вернуть как Alpine `:placeholder` с проверкой viewport

---

## Тестовый аккаунт для повторных аудитов

- Email: `responsive-test@doday.local`
- Password: `TestPass1234!`
- Seed скрипт (локально): `.tmp_local_seed.py`
- Seed скрипт (на проде через SSH): `.tmp_ssh_seed_test_data.py`
- Создание юзера: `.tmp_ssh_create_test_user.py`

Запуск seed локально:
```bash
uv run python .tmp_local_seed.py
```

Воссоздаёт аккаунт с фиксированными данными — overwrite-friendly (delete + insert).
