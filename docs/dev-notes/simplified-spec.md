# simplified-spec.md — упрощённая версия Doday

## Контекст

Полный Doday (60+ фич) сильно перегружен для обычного юзера который просто хочет «записать задачу и отметить когда сделал». Эта спека описывает **параллельную** упрощённую версию.

**Жёсткое правило**: ничего из существующего функционала не удалять. Simplified mode — отдельные роуты `/app/simple/*` + переключатель в settings.

## Целевой юзер

Не школьник-индивидуал с тонной задач. Просто:
- Взрослый который хочет не забыть купить молоко
- Школьник у которого 3-5 задач/день
- Любой кто открыл Doday первый раз и не хочет учиться

## Что входит (essentials)

| # | Фича | Источник в обычном Doday |
|---|---|---|
| 1 | **Список задач на сегодня** | `today.html` |
| 2 | **Inbox** (задачи без даты) | `today.html` Inbox tab |
| 3 | **Добавить задачу** (текст + опц. дата) | `quick_add.html` simplified |
| 4 | **Отметить выполненной** (чекбокс) | `task_row.html` checkbox |
| 5 | **Удалить** (свайп / X) | существует |
| 6 | **Редактировать текст** (клик по тексту) | существует inline-edit |
| 7 | **Тема light/dark/system** | `_partials/topbar.html` |
| 8 | **Логин / Логаут** | базовое |
| 9 | **Mini App в Telegram** (уже есть) | `/miniapp/*` (этот mode уже simple) |

## Что НЕ входит (deliberately)

| Фича | Почему не нужна обычному юзеру |
|---|---|
| Проекты / секции / лейблы | Усложняет, добавляет 3 уровня группировки |
| Фильтры с DSL | Юзер не пишет код |
| Канбан-доска | Нужен team / project context |
| Календарь / weekly view | Today + Upcoming достаточно |
| Pomodoro | Нишевый, требует обучения |
| Статистика / activity | "Заработал karma" — не цель обычного юзера |
| Bulk-actions | Тяжёлое UX, для power-users |
| Templates | Не нужны если задач 3-5 |
| Импорт / экспорт | Нет данных для миграции у нового юзера |
| Backup | Доверь сервису |
| Pricing / billing | Бесплатно вся базовая часть |
| Help / FAQ / changelog | "Просто работает" |
| Shared projects / invitations | Team-feature |
| Comments / subtasks | Усложнение задачи |
| Recurring rules | "Каждый день" есть как 1 чекбокс |
| Reminders | Push для today обязателен, кастомные — нет |
| Sidebar навигация | Только bottom-nav (Today / Inbox / Settings) |

## Архитектура

### Роуты

- `/app/simple/today` — список сегодняшних задач
- `/app/simple/inbox` — задачи без даты
- `/app/simple/add` (POST) — создать задачу из формы
- `/app/simple/settings` — минимальные настройки (тема, выход, переключение в full mode)
- `/app/simple/task/{id}/done` (POST HTMX) — toggle done
- `/app/simple/task/{id}/delete` (POST HTMX) — удалить

### Шаблоны

- `templates/simple/_base.html` — extends ничего, свой layout, bottom-nav (Today / Inbox / Settings)
- `templates/simple/today.html`
- `templates/simple/inbox.html`
- `templates/simple/settings.html`
- `templates/simple/_partials/task_row.html`
- `templates/simple/_partials/add_form.html`

### Переключение между mode'ами

- В `/app/settings` (full mode) — карточка «Попробовать упрощённый интерфейс» → переход на `/app/simple/today`
- В `/app/simple/settings` — кнопка «Вернуть полный интерфейс» → переход на `/app/today`
- Сохранение предпочтения: `localStorage.dodayPreferredMode = 'simple' | 'full'`. Authenticated landing redirect выбирает по нему.
- НЕ требует DB-миграции и нового column'а на users — localStorage достаточно

### Стиль

- Соблюдает `design.md` v1.0 (палитра + типографика + компоненты)
- Использует те же `--bg`, `--text`, `--accent` CSS vars
- Кнопки `.btn-primary` / `.btn-ghost` оттуда
- Mobile-first, max-width 480px (single column)
- Bottom-nav с 3 кнопками: Today, Inbox, Settings

## Поведение auth-flow

- /auth/login → redirect determined by `localStorage.dodayPreferredMode`
- если 'simple' → `/app/simple/today`
- если 'full' или undefined → `/app/today` (default)

## Тесты

- `tests/test_simple_routes.py`
- Cover: GET /app/simple/today (200), POST add (201 + redirect), POST done (200), POST delete (200)
- Auth required для всех
- Использует те же service'ы `app/tasks/service.py` под капотом — никакой дубликации бизнес-логики

## Что НЕ ломаем (compatibility checklist)

- [ ] `/app/today` работает как раньше
- [ ] `/app/inbox` работает
- [ ] /app/settings показывает новую карточку, остальное без изменений
- [ ] Все 650+ существующих тестов проходят
- [ ] miniapp/* не трогается (он уже simple-mode для Telegram)
- [ ] Никаких database миграций
- [ ] Pre-commit зелёный (ruff/mypy/jinja)

## Этапы реализации

### Phase 5.1 — спец (этот файл) ✅
### Phase 5.2 — settings toggle button (в существующем `/app/settings`)
### Phase 5.3 — `/app/simple/today` route + template + 1 unit-test
### Phase 5.4 — `/app/simple/inbox` + add/done/delete
### Phase 5.5 — auth-flow redirect logic

В этой session: 5.1 + 5.2 + 5.3 (минимальный proof of concept). Phase 5.4-5.5 — следующая итерация по запросу.

## Open вопросы (для пользователя)

1. Bottom-nav цвета — те же что в Mini App? (`var(--accent)` подсветка active)
2. Add-form — модал или отдельная страница? Сейчас прототип = отдельная страница `simple/add` (mobile-friendlier)
3. Сохранять `preferred_mode` в users.preferences? (на следующей итерации, не блокирует)
