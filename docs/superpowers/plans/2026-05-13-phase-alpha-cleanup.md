# Phase α — Aggressive cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Удалить 9 lazy-модулей + audience-mode, скрыть UI-surface school-модуля, обновить тесты/документацию. Спецификация — `docs/superpowers/specs/2026-05-13-doday-simplify-and-teams-design.md`. Phase α из 4 (после идут β UI, γ comments, δ teams — отдельными planами).

**Architecture:** Каждый task = отдельный модуль (или группа связанных файлов) → один atomic commit. Order: сначала тесты для удаления и удаление кода, в конце — одна Alembic-миграция, drop'ающая все таблицы скопом + drop column `users.audience`. Тестовая суита после каждого task green; migration применяется в last task с предварительным `pg_dump` backup'ом на проде.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Pydantic v2 + Jinja2 + pytest-asyncio. Pre-commit (ruff + mypy strict + jinja-linter). Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`.

---

## File Structure

**Удаляемые директории** (rm -rf):

```
app/gamification/       app/gamification/{achievements,daily,models,service}.py
app/achievements/       app/achievements/{router,service}.py
app/mood/               (router, service, models, schemas)
app/habits/             (router, service, models, schemas)
app/time_tracking/      (router, service, models, schemas)
app/company/            (router, service, schemas — standup widget)
app/user_templates/     (router, service, models, schemas)
app/custom_filters/     (router, service, models, schemas)
app/calendar_feed/      (router, service, models, schemas — .ics-feed)
app/links/              (router, service, models, schemas — task links)
```

**Удаляемые тестовые файлы** (`tests/`):

```
test_achievements.py        test_school_streak.py
test_audience.py            test_sprint_widget.py
test_audience_switch.py     test_standup.py
test_calendar_feed.py       test_streak_chip.py
test_custom_filters.py      test_subject_chips.py
test_habits.py              test_task_links.py
test_mood.py                test_time_tracking.py
test_today_by_subject.py    test_user_templates.py
test_welcome_flow.py
```

**Модифицируемые файлы:**

```
app/main.py                                    убрать 12 imports + 12 include_router
app/auth/models.py                             убрать users.audience column
app/auth/router.py                             убрать audience param из register
app/auth/schemas.py                            убрать audience field
app/auth/service.py                            заменить _starter_samples_for(audience) → _starter_samples()
app/profile/router.py                          убрать update_audience endpoint
app/digest/service.py                          убрать _audience_line + audience usage
app/views/router.py                            убрать audience==school branch в /app/today
app/school/router.py                           удалить today_schedule endpoint
app/school/__init__.py                         оставить только parser-bits для будущей активации
app/templates/base.html                        sidebar — убрать audience-conditional items
app/templates/today.html                       убрать include для widgets habits/mood/streaks/sprints
app/templates/profile.html                     убрать audience-switcher form
app/templates/landing.html                     убрать упоминания удалённых features
app/templates/pricing.html                     убрать упоминания удалённых features

alembic/versions/0028_drop_lazy_modules.py     новая migration (создаётся в Task 11)
PROGRESS.md                                    запись «α cleanup done»
CLAUDE.md                                      убрать AUDIENCE MODEL секцию
```

**Acceptance после всех tasks:**

- `git status` чистый, нет references на удалённые модули.
- `uv run pre-commit run --all-files` зелёный.
- `uv run pytest -q` зелёный (~480 тестов).
- `uv run alembic upgrade head` локально работает.
- После deploy: `python scripts/smoke_test.py https://getdoday.ru` 23/23 green.
- Manual smoke: `/app/today`, `/app/inbox`, `/app/projects/<id>`, `/app/profile`, `/miniapp/` рендерятся без 500.

---

## Task 1: Backup перед миграцией

**Files:**
- Create: `../doday-pre-α-cleanup.bundle` (git bundle)
- Create on prod: `/tmp/doday-pre-α-cleanup.sql` (pg_dump)

Это **первый и обязательный** task. Без backup'a остальные шаги необратимые.

- [ ] **Step 1: Git tag + bundle на локалке**

```bash
git tag pre-alpha-cleanup HEAD
git bundle create ../doday-pre-alpha-cleanup.bundle --all
ls -la ../doday-pre-alpha-cleanup.bundle
# expect: ~1.5MB file
```

- [ ] **Step 2: pg_dump на проде через SSH**

Создать `.tmp_backup_prod_db.py`:

```python
import os, paramiko
SSH_PASS = open('.env', encoding='utf-8').read().split('SSH_PASS=')[1].split('\n')[0].strip()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('getdoday.ru', port=22, username='getdoday', password=SSH_PASS, timeout=20, look_for_keys=False, allow_agent=False)
env_lines = c.exec_command('cat /var/www/getdoday/data/www/getdoday.ru/app/.env')[1].read().decode()
db_user = next(l.split('=',1)[1].strip() for l in env_lines.splitlines() if l.startswith('DB_USER='))
db_pass = next(l.split('=',1)[1].strip() for l in env_lines.splitlines() if l.startswith('DB_PASS='))
db_name = next(l.split('=',1)[1].strip() for l in env_lines.splitlines() if l.startswith('DB_NAME='))
cmd = f"PGPASSWORD='{db_pass}' pg_dump -h 127.0.0.1 -U {db_user} -d {db_name} -F c -f /tmp/doday-pre-alpha-cleanup.sql"
_, out, err = c.exec_command(cmd, timeout=60)
print('stderr:', err.read().decode())
_, out, _ = c.exec_command('ls -la /tmp/doday-pre-alpha-cleanup.sql', timeout=10)
print(out.read().decode())
c.close()
```

Run: `uv run python .tmp_backup_prod_db.py`
Expected: file `/tmp/doday-pre-alpha-cleanup.sql` ~100KB-1MB на проде.

- [ ] **Step 3: Push tag в origin**

```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" pre-alpha-cleanup
```

Backup готов. Дальше можно безопасно удалять.

---

## Task 2: Удаление gamification + achievements

**Files:**
- Delete: `app/gamification/` (4 файла)
- Delete: `app/achievements/` (2 файла)
- Delete: `tests/test_achievements.py`
- Modify: `app/main.py` — убрать imports + include_router

- [ ] **Step 1: Удалить директории gamification + achievements**

```bash
rm -rf app/gamification app/achievements
ls app/gamification app/achievements 2>&1
# Expected: cannot access
```

- [ ] **Step 2: Удалить тестовый файл**

```bash
rm -f tests/test_achievements.py
```

- [ ] **Step 3: Из `app/main.py` убрать imports + include_router**

Открыть `app/main.py`, удалить две строки в imports-секции:
```python
from app.achievements.router import router as achievements_router
```

И одну в секции `app.include_router(...)`:
```python
app.include_router(achievements_router)
```

- [ ] **Step 4: Прогнать тесты**

```bash
uv run pytest -q 2>&1 | tail -10
```

Expected: green (test_achievements удалён, references остальных тестов в порядке).
Если падают — ищи `import app.gamification` или `import app.achievements` в других тестах:
```bash
grep -rE "app\.(gamification|achievements)" tests/ app/ --include="*.py"
```

- [ ] **Step 5: Pre-commit + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
chore(cleanup-α): удалил gamification + achievements модули

Удалил app/gamification/ (XP, daily challenges, models) и
app/achievements/ (router, service). 16 ачивок и XP-эвенты больше
не считаются. Тесты test_achievements.py удалены.

Часть фазы α агрессивного упрощения. Spec:
docs/superpowers/specs/2026-05-13-doday-simplify-and-teams-design.md
EOF
)"
```

---

## Task 3: Удаление mood-tracker

**Files:**
- Delete: `app/mood/` (router, service, models, schemas)
- Delete: `tests/test_mood.py`
- Modify: `app/main.py` — убрать mood imports + include_router
- Modify: `app/templates/today.html` — убрать `{% include "_partials/mood_widget.html" %}` если есть
- Delete: `app/templates/_partials/mood_widget.html` если есть

- [ ] **Step 1: Удалить директорию + тесты**

```bash
rm -rf app/mood tests/test_mood.py
rm -f app/templates/_partials/mood_widget.html
```

- [ ] **Step 2: Найти и убрать include mood widget**

```bash
grep -rn "mood" app/templates/ 2>&1 | head -10
```

Удалить найденные `{% include "..mood.." %}` строки.

- [ ] **Step 3: main.py — убрать import + include_router**

Удалить:
```python
from app.mood.router import router as mood_router
app.include_router(mood_router)
```

- [ ] **Step 4: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -5
```

Expected: оба green.

- [ ] **Step 5: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил mood-tracker"
```

---

## Task 4: Удаление habits

**Files:**
- Delete: `app/habits/`
- Delete: `tests/test_habits.py`
- Modify: `app/main.py`
- Modify: `app/templates/today.html` + `app/templates/base.html` (sidebar) если habits-link

- [ ] **Step 1: Удалить директорию + тесты**

```bash
rm -rf app/habits tests/test_habits.py
```

- [ ] **Step 2: Найти упоминания habits в templates + Python**

```bash
grep -rE "habit" app/templates/ app/main.py 2>&1 | grep -v __pycache__ | head -15
```

- [ ] **Step 3: Убрать import + include_router в main.py**

Удалить:
```python
from app.habits.router import router as habits_router
app.include_router(habits_router)
```

- [ ] **Step 4: Убрать habits-link из sidebar в base.html**

Открыть `app/templates/base.html`, найти секцию sidebar (обычно блок `<aside>` или `<nav>`), удалить блок ссылки на `/app/habits`.

- [ ] **Step 5: Убрать habits-include из today.html (если есть)**

```bash
grep -n "habit" app/templates/today.html 2>&1
```

Если найдено — удалить.

- [ ] **Step 6: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил habits-tracker"
```

---

## Task 5: Удаление time_tracking + sprint_widget + streak_chip

Эти три связаны (отображают time/streaks/sprints) — режу вместе.

**Files:**
- Delete: `app/time_tracking/`
- Delete: `tests/test_time_tracking.py`, `tests/test_sprint_widget.py`, `tests/test_streak_chip.py`, `tests/test_school_streak.py`
- Delete: views/templates для sprint/streak (если отдельные файлы)
- Modify: `app/main.py`
- Modify: `app/templates/today.html`, `app/templates/base.html` — убрать widget includes

- [ ] **Step 1: Найти views для sprint/streak**

```bash
find app/views -name "*sprint*" -o -name "*streak*" 2>&1
find app/templates -name "*sprint*" -o -name "*streak*" 2>&1
```

- [ ] **Step 2: Удалить найденные файлы + директорию time_tracking + тесты**

```bash
rm -rf app/time_tracking
rm -f tests/test_time_tracking.py tests/test_sprint_widget.py tests/test_streak_chip.py tests/test_school_streak.py
# Удалить найденные sprint/streak view-файлы и templates (по списку из Step 1)
```

- [ ] **Step 3: main.py — убрать import + include_router для time_tracking**

```python
# Remove:
from app.time_tracking.router import router as time_tracking_router
app.include_router(time_tracking_router)
```

- [ ] **Step 4: Убрать включения widget'ов в today.html / base.html**

```bash
grep -nE "sprint|streak|time_track" app/templates/today.html app/templates/base.html 2>&1
```

Удалить найденные include/блоки.

- [ ] **Step 5: Найти ссылки в Python**

```bash
grep -rE "time_tracking|sprint_widget|streak_chip" app/ --include="*.py" 2>&1 | grep -v __pycache__
```

Если есть imports/usages — почистить (например в `app/views/router.py`).

- [ ] **Step 6: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -10
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил time-tracking + sprint + streak widgets"
```

---

## Task 6: Удаление company + standup widget

**Files:**
- Delete: `app/company/`
- Delete: `tests/test_standup.py`
- Modify: `app/main.py`
- Modify: `app/views/router.py` — убрать audience=='company' ветку
- Modify: `app/templates/today.html` — убрать standup widget include

- [ ] **Step 1: Удалить директорию + тест**

```bash
rm -rf app/company tests/test_standup.py
```

- [ ] **Step 2: main.py — убрать import + include_router**

```python
# Remove:
from app.company.router import router as company_router
app.include_router(company_router)
```

- [ ] **Step 3: Убрать standup-include в today.html**

```bash
grep -n "standup\|company" app/templates/today.html 2>&1
```

Удалить найденные строки.

- [ ] **Step 4: Убрать ссылку в app/views/router.py**

```bash
grep -n "company" app/views/router.py 2>&1
```

Если есть — убрать.

- [ ] **Step 5: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил company standup widget"
```

---

## Task 7: Удаление user_templates + custom_filters

Связанные power-user фичи, режу вместе.

**Files:**
- Delete: `app/user_templates/`, `app/custom_filters/`
- Delete: `tests/test_user_templates.py`, `tests/test_custom_filters.py`
- Modify: `app/main.py`
- Modify: `app/templates/base.html` — убрать sidebar-link «Фильтры»

- [ ] **Step 1: Удалить директории + тесты**

```bash
rm -rf app/user_templates app/custom_filters
rm -f tests/test_user_templates.py tests/test_custom_filters.py
```

- [ ] **Step 2: main.py — убрать 4 строки**

```python
# Remove (3 imports + 3 include_router):
from app.custom_filters.router import router as custom_filters_router
from app.user_templates.router import router as user_templates_router
from app.user_templates.router import save_router as save_as_template_router

app.include_router(custom_filters_router)
app.include_router(user_templates_router)
app.include_router(save_as_template_router)
```

- [ ] **Step 3: Убрать sidebar-link «Фильтры» в base.html**

```bash
grep -n "filters\|Фильтр" app/templates/base.html 2>&1
```

Удалить link / nav-item.

- [ ] **Step 4: Проверить task_detail / task_row references**

```bash
grep -rE "save.*template|user_template|custom_filter" app/templates/ 2>&1 | head -10
```

Удалить найденные кнопки/блоки.

- [ ] **Step 5: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -10
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил user_templates + custom_filters"
```

---

## Task 8: Удаление calendar_feed (.ics) + links

**Files:**
- Delete: `app/calendar_feed/`, `app/links/`
- Delete: `tests/test_calendar_feed.py`, `tests/test_task_links.py`
- Modify: `app/main.py`
- Modify: `app/templates/profile.html` — убрать «Календарь .ics» секцию

- [ ] **Step 1: Удалить директории + тесты**

```bash
rm -rf app/calendar_feed app/links
rm -f tests/test_calendar_feed.py tests/test_task_links.py
```

- [ ] **Step 2: main.py — убрать 5 строк**

```python
# Remove imports (4):
from app.calendar_feed.router import router as calendar_feed_router
from app.calendar_feed.router import token_router as calendar_token_router
from app.links.router import graph_router as links_graph_router
from app.links.router import router as links_router

# Remove include_router (4):
app.include_router(calendar_feed_router)
app.include_router(calendar_token_router)
app.include_router(links_router)
app.include_router(links_graph_router)
```

- [ ] **Step 3: Убрать «Календарь .ics» секцию в profile.html**

```bash
grep -n "ics\|calendar_feed\|webcal" app/templates/profile.html 2>&1
```

Удалить блок.

- [ ] **Step 4: Убрать links-UI в task_detail**

```bash
grep -rE "task.*link|links" app/templates/ --include="*.html" 2>&1 | grep -v "include.*nav\|sidebar" | head -10
```

Удалить блок «Связанные задачи».

- [ ] **Step 5: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -10
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): удалил calendar_feed (.ics) + task_links"
```

---

## Task 9: Скрытие school UI-surface (модуль остаётся)

School module **остаётся в коде** на будущее (когда юзер купит прокси). Сейчас скрываем UI-surfacing:

**Files:**
- Modify: `app/views/router.py` — убрать `today_schedule` ветку для audience='school'
- Modify: `app/templates/today.html` — убрать today_schedule widget include
- Modify: `app/templates/base.html` — убрать sidebar-link «Расписание»
- Delete (если есть отдельный widget-файл): `app/templates/_partials/today_schedule.html`, `app/templates/_partials/subject_chips.html`
- Delete: `tests/test_subject_chips.py`, `tests/test_today_by_subject.py`

- [ ] **Step 1: Удалить тесты школьных UI**

```bash
rm -f tests/test_subject_chips.py tests/test_today_by_subject.py
```

- [ ] **Step 2: Убрать audience=='school' ветку в views/router.py**

Открыть `app/views/router.py`, найти примерно такой блок:
```python
if user.audience == "school" and today:
    # ... выдача расписания ...
```
Удалить целиком (включая закрытие if).

- [ ] **Step 3: Удалить partial-templates**

```bash
ls app/templates/_partials/today_schedule.html app/templates/_partials/subject_chips.html 2>&1
rm -f app/templates/_partials/today_schedule.html app/templates/_partials/subject_chips.html
```

- [ ] **Step 4: Убрать includes в today.html + sidebar в base.html**

```bash
grep -nE "today_schedule|subject_chip" app/templates/today.html 2>&1
grep -nE "/app/school\|Расписание" app/templates/base.html 2>&1
```

Удалить найденные строки.

- [ ] **Step 5: school router всё ещё mounted — НЕ ТРОГАТЬ**

```bash
grep -n "school" app/main.py 2>&1
# Expected: 2 строки (import + include_router) — оба ОСТАЮТСЯ
```

- [ ] **Step 6: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -10
uv run pre-commit run --all-files 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "chore(cleanup-α): скрыл school UI-surface (код остаётся для будущего активирования)"
```

---

## Task 10: Удаление audience-mode из кода

Это самый сложный task — `audience` пронизывает auth/welcome/profile/digest/views.

**Files:**
- Modify: `app/auth/models.py` — убрать `audience` column (только модель, миграция в Task 11)
- Modify: `app/auth/schemas.py` — убрать audience field из RegisterIn
- Modify: `app/auth/router.py` — убрать audience param в register endpoint
- Modify: `app/auth/service.py` — `_starter_samples_for(audience)` → `_starter_samples()`
- Modify: `app/profile/router.py` — удалить `update_audience` endpoint
- Modify: `app/digest/service.py` — убрать `_audience_line` + audience usage
- Modify: `app/views/router.py` — убрать audience-conditional logic (если осталась после Task 9)
- Modify: `app/templates/profile.html` — убрать audience-switcher form
- Modify: `app/templates/welcome.html` (или register.html) — убрать audience-выбор
- Delete: `tests/test_audience.py`, `tests/test_audience_switch.py`, `tests/test_welcome_flow.py`

- [ ] **Step 1: Удалить тесты audience**

```bash
rm -f tests/test_audience.py tests/test_audience_switch.py tests/test_welcome_flow.py
```

- [ ] **Step 2: Убрать audience column из app/auth/models.py**

Открыть `app/auth/models.py`, найти и удалить строку:
```python
audience: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 3: Убрать audience field из app/auth/schemas.py**

```bash
grep -n "audience" app/auth/schemas.py 2>&1
```

Удалить найденные field-определения в `RegisterIn` / `UserOut` если есть.

- [ ] **Step 4: Убрать audience param из app/auth/router.py**

```bash
grep -n "audience" app/auth/router.py 2>&1
```

Удалить присвоение `audience=aud` в `RegisterIn(...)` вызове. Также убрать `aud = Form(...)` или `Body(...)` если есть.

- [ ] **Step 5: Заменить `_starter_samples_for(audience)` → `_starter_samples()`**

Открыть `app/auth/service.py`. Найти функцию `_starter_samples_for(audience)`:

```python
# До:
def _starter_samples_for(audience: str | None) -> list[StarterSample]:
    if audience == "school":
        return [...]
    elif audience == "company":
        return [...]
    return [...]
```

Заменить на:

```python
# После:
def _starter_samples() -> list[StarterSample]:
    """Универсальные стартовые задачи для всех новых юзеров."""
    return [
        StarterSample(title="Попробовать Doday — посмотри Today, Inbox, Projects"),
        StarterSample(title="Создать свой первый проект"),
        StarterSample(title="Добавить задачу с приоритетом /// и датой 'завтра'"),
    ]
```

И вызов в register_user:
```python
# До:
samples = _starter_samples_for(user.audience)
# После:
samples = _starter_samples()
```

- [ ] **Step 6: Удалить update_audience в app/profile/router.py**

```bash
grep -nC 3 "audience" app/profile/router.py 2>&1
```

Найти endpoint `@router.patch("/api/profile/audience")` или подобный. Удалить функцию целиком.

- [ ] **Step 7: Убрать _audience_line + audience в app/digest/service.py**

```bash
grep -n "audience" app/digest/service.py 2>&1
```

Найти функцию `_audience_line(audience)` — удалить целиком. Также убрать вызовы `_audience_line(user.audience)` (заменить на нейтральный текст или удалить строку).

- [ ] **Step 8: Убрать audience в app/views/router.py (если осталось после Task 9)**

```bash
grep -n "audience" app/views/router.py 2>&1
```

Удалить остаточные ветки.

- [ ] **Step 9: Убрать audience-switcher в profile.html**

```bash
grep -nC 2 "audience" app/templates/profile.html 2>&1
```

Удалить form с radio-кнопками выбора audience.

- [ ] **Step 10: Убрать audience-выбор в welcome.html / register**

```bash
ls app/templates/welcome.html app/templates/auth/register.html 2>&1
grep -n "audience" app/templates/welcome.html app/templates/auth/register.html 2>&1 | head -10
```

Удалить блоки выбора аудитории.

- [ ] **Step 11: Финальная проверка**

```bash
grep -rE "audience" app/ tests/ --include="*.py" --include="*.html" 2>&1 | grep -v __pycache__ | head -10
# Expected: только школьные модели где audience='school' хардкод-строка БЕЗ user.audience
```

Если что-то осталось — почистить.

- [ ] **Step 12: pytest + pre-commit**

```bash
uv run pytest -q 2>&1 | tail -15
uv run pre-commit run --all-files 2>&1 | tail -5
```

Expected: green. Если падают тесты — поправь предположения (тесты могли использовать default audience).

- [ ] **Step 13: Commit**

```bash
git add -A
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
chore(cleanup-α): удалил audience-mode полностью

users.audience column удалится отдельной миграцией следующим коммитом.
В коде убрал: audience field в auth/schemas, audience-param в register,
_starter_samples_for(audience) → _starter_samples() единый шаблон,
update_audience endpoint в profile, _audience_line в digest,
audience-ветки в views, switcher в profile.html, выбор в welcome.html.
EOF
)"
```

---

## Task 11: Alembic migration — drop tables + drop column

После того как код не ссылается на удалённые таблицы — пишем единую migration.

**Files:**
- Create: `alembic/versions/0028_drop_lazy_modules.py`

- [ ] **Step 1: Создать `alembic/versions/0028_drop_lazy_modules.py`**

```python
"""drop lazy modules + audience column

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK cascade — order matters
    op.execute("DROP TABLE IF EXISTS user_achievements CASCADE")
    op.execute("DROP TABLE IF EXISTS user_progress CASCADE")
    op.execute("DROP TABLE IF EXISTS xp_events CASCADE")
    op.execute("DROP TABLE IF EXISTS habit_completions CASCADE")
    op.execute("DROP TABLE IF EXISTS habits CASCADE")
    op.execute("DROP TABLE IF EXISTS mood_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS time_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS user_templates CASCADE")
    op.execute("DROP TABLE IF EXISTS custom_filters CASCADE")
    op.execute("DROP TABLE IF EXISTS task_links CASCADE")
    # users.audience
    op.drop_column("users", "audience")


def downgrade() -> None:
    raise NotImplementedError(
        "Aggressive cleanup is one-way; restore from pre-alpha-cleanup tag "
        "or pg_dump backup (/tmp/doday-pre-alpha-cleanup.sql on prod) if needed."
    )
```

`DROP TABLE IF EXISTS … CASCADE` — безопасно если таблица отсутствует (например в dev-БД свежей).

- [ ] **Step 2: Прогнать миграцию локально**

Сначала убедись что локальный Postgres запущен (`pg_ctl status`):

```bash
uv run alembic upgrade head 2>&1 | tail -10
```

Expected: `INFO [alembic.runtime.migration] Running upgrade 0027 -> 0028`.

Если падает — посмотри stderr, скорее всего FK constraint в порядке таблиц. Список выше специально расположен в правильном порядке.

- [ ] **Step 3: Проверить что схема корректна**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from app.db import get_engine

async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        r = await conn.execute(text(\"\"\"
            SELECT column_name FROM information_schema.columns
            WHERE table_name='users' AND column_name='audience'
        \"\"\"))
        rows = r.fetchall()
        print('audience column rows:', rows)
        r = await conn.execute(text(\"\"\"
            SELECT table_name FROM information_schema.tables
            WHERE table_name IN ('xp_events','habits','mood_entries','time_logs',
                                 'user_templates','custom_filters','task_links')
        \"\"\"))
        rows = r.fetchall()
        print('lazy tables remaining:', rows)

asyncio.run(main())
"
```

Expected:
```
audience column rows: []
lazy tables remaining: []
```

- [ ] **Step 4: pytest**

```bash
uv run pytest -q 2>&1 | tail -10
```

Expected: green. Pytest пересоздаёт test-БД, миграции прогоняются автоматом.

- [ ] **Step 5: pre-commit + commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -5
git add alembic/versions/0028_drop_lazy_modules.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
chore(cleanup-α): миграция 0028 — drop lazy modules

Удаляет 10 таблиц: xp_events, user_progress, user_achievements,
habits, habit_completions, mood_entries, time_logs, user_templates,
custom_filters, task_links. Drops users.audience column.

CASCADE убирает все FK references. Downgrade не реализован —
восстанавливать из pre-alpha-cleanup tag или pg_dump backup'a.
EOF
)"
```

---

## Task 12: Обновление documentation

**Files:**
- Modify: `PROGRESS.md` — добавить запись о завершении α
- Modify: `CLAUDE.md` — убрать секцию «AUDIENCE MODEL 2026-05-04»
- Modify: `~/.claude/projects/c--www-Yaroslav-SchoolProject/memory/project_pivot.md` — обновить

- [ ] **Step 1: Append запись в PROGRESS.md**

```bash
# Откройте PROGRESS.md, добавьте в начало:
```

Запись:
```markdown
## 2026-05-13 — Phase α: aggressive cleanup завершён

Удалены 9 lazy-модулей (gamification, achievements, mood, habits,
time_tracking, company, user_templates, custom_filters, calendar_feed,
links) + audience-mode. School-модуль остаётся в коде на случай
будущей активации через прокси/токен.

Migration: 0028_drop_lazy_modules.py — drop 10 tables + users.audience.
Тесты: ~150 удалены, ~480 остаются зелёные.
Smoke: 23/23 GREEN.
Backup до миграции: pre-alpha-cleanup git-tag + /tmp/doday-pre-alpha-cleanup.sql на проде.

State: PIDs uvicorn ?, port 8011, web alive.
Next: Phase β — UI redesign (light theme default, sidebar 4 пункта, task row single-line).
```

- [ ] **Step 2: Убрать AUDIENCE MODEL секцию из CLAUDE.md**

```bash
grep -n "AUDIENCE MODEL" CLAUDE.md 2>&1
```

Найти секцию (обычно начинается с `## AUDIENCE MODEL 2026-05-04`) и удалить её целиком до следующего `##`-заголовка.

- [ ] **Step 3: Обновить project_pivot.md в memory**

Файл: `C:/Users/Yaroslav/.claude/projects/c--www-Yaroslav-SchoolProject/memory/project_pivot.md`.

Добавить в конец абзаца:
```markdown
**2026-05-13 update:** Audience-mode полностью удалён (вместе с
gamification/mood/habits/time-tracking/company/user_templates/custom_filters/calendar_feed/links).
School-модуль сохранён как dormant — активируется когда юзер купит
прокси + токен дневника. Текущий продукт = focused todo + Pomodoro +
comments + (готовятся командные проекты).
```

- [ ] **Step 4: Commit**

```bash
git add PROGRESS.md CLAUDE.md
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "docs(cleanup-α): PROGRESS+CLAUDE обновлены под новый scope"
```

Memory file не в git — закоммитится автоматом через `.claude/memory/`-механизм.

---

## Task 13: Push в master + ждём deploy + smoke

**Files:** —

Финальная проверка end-to-end.

- [ ] **Step 1: Push в master**

```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master 2>&1 | tail -3
```

- [ ] **Step 2: Ждать deploy + alembic upgrade на проде**

Cron-poll каждую минуту делает `git reset --hard origin/master` + `alembic upgrade head` + uvicorn restart. Ожидание ~90 секунд.

```bash
sleep 90
```

- [ ] **Step 3: Smoke test**

```bash
uv run python scripts/smoke_test.py https://getdoday.ru 2>&1 | tail -10
```

Expected: `all 23 green`.

- [ ] **Step 4: Manual check ключевых страниц**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://getdoday.ru/auth/login
curl -s -o /dev/null -w "%{http_code}\n" https://getdoday.ru/auth/register
curl -s -o /dev/null -w "%{http_code}\n" https://getdoday.ru/miniapp/assets/miniapp.js
# Expected: 200 / 200 / 200
```

- [ ] **Step 5: Manual UI check (авторизованным)**

В браузере открыть `https://getdoday.ru/app/today`, `/app/inbox`, `/app/projects`, `/app/profile`.
Ожидание: страницы рендерятся без 500. Sidebar без удалённых links. Profile без audience-switcher.

- [ ] **Step 6: Тест регистрации нового юзера**

Зарегистрируй тестовый аккаунт на свой второй email. Ожидание:
- /welcome — нет выбора аудитории (1 экран)
- /app/today — есть стартовые задачи (универсальные)
- /app/profile — без audience-switcher

Если что-то 500 — посмотри Sentry / uvicorn-log на проде. Скорее всего пропущенный реф на удалённый модуль.

---

# Roadmap фаз β, γ, δ (отдельными планами после α)

Эти фазы будут расписаны через writing-plans после завершения α.

### Phase β — UI redesign

После α много lazy-кода исчезнет, переписывать остаётся меньше. Чанки:
1. Sidebar redesign в `base.html` (4 пункта + projects + footer)
2. Light theme default — обновить `:root` в `base.html`, перевернуть toggle
3. `task_row.html` — переписать в одну строку
4. `landing.html` + `pricing.html` — copy-edit
5. `welcome.html` — 1 экран instead of 3
6. `/app/settings` — слить profile в settings
7. Mini App: default light theme + simplify task_card chips

### Phase γ — Comments UI polish

Backend уже работает.
1. Web `/app/tasks/<id>` — accordion comments под task-detail
2. Mini App `task_sheet.html` — секция comments с Alpine fetch

### Phase δ — Team collab

1. Migration: `project_members` + `project_invitations` таблицы + backfill
2. `tasks.assigned_to` column миграция
3. Service: `is_member`, `is_owner`, `add_member`, `remove_member`
4. Service: `create_invitation`, `accept_invitation`, `revoke_invitation`
5. Permission middleware: `require_project_access`, `require_project_owner`
6. Update existing routes (project/task/section/comment) на membership-check
7. Email-template `app/templates/email/invitation.html`
8. UI: `/app/projects/<id>` — «Поделиться» modal
9. UI: `/invite/<token>` — accept page
10. Tests: `test_project_members.py`, `test_project_invitations.py`, `test_project_permissions.py`, `test_task_assignee.py`

---

## Self-Review (выполнено перед публикацией плана)

**Spec coverage:**
- α удаление 9 модулей ✓ (Tasks 2-8)
- α school UI скрытие ✓ (Task 9)
- α audience-mode полное удаление ✓ (Task 10)
- α migration ✓ (Task 11)
- α tests pruning ✓ (распределено по Tasks 2-10)
- α docs update ✓ (Task 12)
- α backup ✓ (Task 1)
- β/γ/δ — отнесено в roadmap (отдельные планы после α завершения)

**Placeholder scan:** проверено — нет TBD/TODO в самом плане. Точные пути файлов везде, exact commands, expected output.

**Type consistency:**
- `_starter_samples_for(audience)` упоминается одним именем во всех Tasks ✓
- `pre-alpha-cleanup` git tag — одно имя ✓
- migration revision = `0028` ✓ (consistent с alembic next-revision)

**Scope check:** план **только** фаза α. β/γ/δ — отдельные планы после α. Каждый task atomic, runnable независимо после backup'a.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-13-phase-alpha-cleanup.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent на каждый task, ревью между task'ами, быстрая итерация. Хорошо для α потому что чанки independent (по модулю).

**2. Inline Execution** — выполнить tasks в текущей сессии через executing-plans, batch с checkpoints для review.

**Which approach?**
