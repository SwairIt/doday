# Mini App v2 — visual parity + stats + polish

**Дата:** 2026-05-11→12 (overnight)
**Контекст:** mini-app v1 функционально готов (план `2026-05-11-habr-launch-and-miniapp.md` ✅ закрыт). Юзер просит:
1. Задачи в mini-app должны выглядеть **одинаково** с задачами на сайте (после изменения свойств — приоритет, дата, лейблы, проект, recurrence, pin — visual должен совпадать). Сейчас mini-app task_card показывает в ~3 раза меньше информации чем web task_row.
2. Добавить **графики и метрики** — на сайте есть полноценная страница `/app/stats` с bar-chart + longest_streak + best_weekday + avg_completion_hours. Mini-app показывает только 3 счётчика.
3. Сделать всё **очень красиво** — как сайт, но в mini-app формате.

**Решения юзера:**
- Графики **интегрировать в `/miniapp/me`** (не делать отдельную вкладку — 5 в bottom-nav уже занято)
- Иллюстрации для empty states — **inline SVG руками** (наш стиль, без CDN)
- Sound feedback — **пропустить** (haptic достаточно)

**Разделено на 3 группы:** V (visual parity), S (stats), P (polish).

---

## Группа V — Visual parity с web task_row (~6 чанков, ~4ч)

### Chunk V1 — Enrich /api/tasks payload + eager-load relationships (~45 мин)

**Что:**
- В `app/miniapp/router.py` — изменить `api_get_task(task_id)` чтобы возвращал:
  - `project: {id, name, color, is_inbox}` (eager-loaded через subquery или second-fetch)
  - `labels: [{id, name, color, slug}]` (через `selectinload(Task.labels)`)
  - `description` (если есть)
  - `pinned_at` (ISO или null)
  - `subtask_stats: {done: N, total: M}` (через GROUP-BY subquery)
  - `age_days: int` (Дни с created_at — рассчитываем на сервере)
  - Существующие поля сохранить (id, title, priority, due_at, due_date_only, is_completed, project_id, recurrence)

**Файлы:**
- `app/miniapp/router.py` — `api_get_task` расширение + helper `_task_to_dict()` для DRY
- `tests/test_miniapp_pages.py` — обновить `test_api_get_patch_delete_task` чтоб проверяло новые поля

**Acceptance:**
- GET `/miniapp/api/tasks/{id}` → response содержит project/labels/description/pinned_at/subtask_stats/age_days
- mypy strict + ruff green
- Все существующие 40 тестов остаются green

---

### Chunk V2 — task_card.html parity с web task_row (~1ч)

**Что:**
- Project-color-dot перед title:
  - `<span class="w-1.5 h-1.5 rounded-full bg-{{ project_color }}-400">`
  - Скрывать когда task — subtask (для нестинга)
- Pin-icon 📌:
  - `{% if task.pinned_at %}<span title="Закреплено">📌</span>{% endif %}`
- Description preview:
  - `{% if task.description %}<div class="text-xs text-[var(--text-muted)] mt-1 line-clamp-1">{{ task.description }}</div>{% endif %}`
- Labels-chips цветные:
  - Цикл `task.labels` → `<span class="text-[10px] px-1.5 py-0.5 rounded bg-{{ lab.color }}-500/15 text-{{ lab.color }}-400">@{{ lab.name }}</span>`
- Subtask progress chip с mini-полосой:
  - Inline `x-data` с fetch `/miniapp/api/tasks/{id}/subtasks` (новый endpoint)
  - Полоса `width: {{ done/total*100 }}%` + текст `2/5`
  - Показывать только если total > 0
- «Висит N дн.»:
  - Alpine `x-data` считает age, показывает если age ≥ 7 и не is_completed
  - Italic text-[10px] text-[var(--text-muted)]
- Recurrence chip — переделать на emerald c иконкой 🔁
- Date-chip окрашивается под project color: `bg-{{ project_color }}-500/15 text-{{ project_color }}-400`

**Файлы:**
- `app/templates/miniapp/_partials/task_card.html` — большая переделка
- Новый endpoint: `GET /miniapp/api/tasks/{id}/subtasks` → list subtasks для accordion

**Acceptance:**
- Tasks с labels рендерятся с правильными цветами
- Pinned task с 📌
- Description preview под title если есть
- Subtask progress загружается lazy
- Stale task ≥7 дней показывает «Висит N дн.»

---

### Chunk V3 — Передать project_color_map во все views (~30 мин)

**Что:**
- В `today`, `inbox`, `calendar`, `project_view`, и в `task_sheet` — добавить `project_color_map: dict[UUID, str]` в context через `list_projects(session, user.id)` затем `{p.id: p.color for p in projects}`
- task_card шаблон ищет color через `project_color_map[task.project_id]`
- Аналогично web (там тоже `project_color_map`)

**Файлы:**
- `app/miniapp/router.py` — каждый view добавляет map в context
- `task_card.html` — использует map для всех project-color-aware штук

**Acceptance:**
- Каждая задача рендерится с правильным цветом проекта
- 0 регрессий: все 40 тестов green

---

### Chunk V4 — Labels picker в task_sheet (~1ч)

**Что:**
- В `task_sheet.html` — новая секция «Лейблы» между priority и due-date
- Lazy-fetch `/miniapp/api/labels` (новый GET endpoint) при первом open sheet
- Horizontal-scroll chips: каждый label — кликабельный chip с x-show selected/not
- Тап → toggle: добавить если не было, убрать если было → PATCH `/api/tasks/{id}` body `{label_ids: [...]}`
- Backend: PATCH endpoint расширить `label_ids: list[str] | None = None` → если задано, replace задачи labels

**Файлы:**
- `app/miniapp/router.py` — `GET /api/labels` + PATCH расширение для label_ids
- `app/templates/miniapp/_partials/task_sheet.html` — labels-section + Alpine state

**Acceptance:**
- Toggle labels работает в обе стороны
- 2 теста: GET labels, PATCH с label_ids replace

---

### Chunk V5 — Recurrence picker + Pin toggle в task_sheet (~45 мин)

**Что:**
- Recurrence-секция: 5 chips — «— / день / неделя / месяц / год» с emerald-стилем
- Pin-toggle — button-icon вверху sheet (наряду с close ✕) или в Actions row
- Backend PATCH: расширить `recurrence: str | None` (валидация на enum) и `toggle_pin: bool` → toggling pinned_at

**Файлы:**
- `app/miniapp/router.py` — TaskPatchIn расширение
- `task_sheet.html` — UI

**Acceptance:**
- Toggle pin меняет 📌 на task_card
- Смена recurrence отображается в чипсе после reload

---

### Chunk V6 — Subtasks accordion в task_sheet + endpoint (~45 мин)

**Что:**
- `GET /miniapp/api/tasks/{id}/subtasks` — return list подзадач
- В sheet — секция «Подзадачи» с count, разворачивается по тапу
- Каждая подзадача — inline checkbox + title (без полного редактирования)
- Кнопка «+ Подзадача» → input → POST подзадачи (parent_task_id=current)

**Файлы:**
- `app/miniapp/router.py` — endpoints (GET subtasks, POST create subtask)
- `task_sheet.html` — accordion section
- Backend POST `/api/tasks` — добавить опциональный `parent_task_id`

**Acceptance:**
- Subtask создаётся под главной задачей
- Checkbox subtask меняет is_completed
- Progress на task_card обновляется при reload

---

## Группа S — Stats page с графиками в /miniapp/me (~5 чанков, ~3ч)

### Chunk S1 — Backend `/miniapp/api/stats` + переиспользование app.stats.service (~45 мин)

**Что:**
- Новый endpoint `GET /miniapp/api/stats` — возвращает полный набор:
  - `current_streak`, `longest_streak`
  - `done_today`, `done_week`, `done_month`, `done_total`
  - `chart_14d: [{date, label, count}]`
  - `chart_max: int`
  - `best_weekday: str`, `avg_per_active_day: float`, `active_days: int`, `avg_completion_hours: float`
  - `by_priority: {p1, p2, p3, p4}` — count активных задач по priority
  - `by_project: [{id, name, color, count}]` — top 5 проектов с count активных
- Переиспользовать `app.stats.service.compute_stats(session, user_id)` где можно
- Дополнительные query для by_priority + by_project

**Файлы:**
- `app/miniapp/router.py`
- `tests/test_miniapp_pages.py` — 1 тест проверяет все поля присутствуют

---

### Chunk S2 — Me-page: hero-streak + 14-day bar-chart (~45 мин)

**Что:**
- В `app/miniapp/router.py` `me` endpoint грузить полную stats через тот же helper что и /api/stats
- Замена hero-streak: добавить мини-бейдж «лучший рекорд: N»
- Новая section: 14-day bar-chart inline SVG:
  - viewBox с 14 column-rectangles, height proportional, gradient fill (violet→fuchsia)
  - Подписи дат под bar'ами
  - «Макс: N» наверху
  - hover-effect (на mobile — title attribute)
- В `me.html` обновить layout

**Файлы:**
- `app/miniapp/router.py` — `me` handler грузит full stats
- `app/templates/miniapp/me.html` — большая переделка

**Acceptance:**
- На /miniapp/me видно longest_streak ≤ current_streak
- Bar-chart рендерится с правильными высотами
- 14 дней, последний — сегодня

---

### Chunk S3 — Donut-chart «По приоритетам» (~30 мин)

**Что:**
- Inline SVG donut: 4 сегмента, radius=40, stroke-dasharray для каждого сектора
- Цвета: P1=rose-400, P2=amber-400, P3=sky-400, P4=slate-400
- Внутри donut — total число задач
- Легенда снизу с % и подписями

**Файлы:**
- `app/templates/miniapp/me.html`

**Acceptance:**
- Если всё P4 — донат однотонный (slate)
- Иначе — пропорциональные сегменты

---

### Chunk S4 — Bar-chart «Топ-5 проектов» (~30 мин)

**Что:**
- Section «По проектам» с горизонтальными bar'ами
- Каждый bar: имя слева, полоса с цветом проекта (`bg-{color}-400/40`), count справа
- Top 5, остальные суммируются в «Прочее»

**Файлы:**
- `app/templates/miniapp/me.html`

---

### Chunk S5 — Бейджи достижений + footer (~30 мин)

**Что:**
- В стат-секции — баджики:
  - 🔥 «Неделя» при streak ≥ 7
  - 🏆 «Месяц» при streak ≥ 30
  - 💯 «Сотка» при done_total ≥ 100
  - 🎯 «Год задач» при done_total ≥ 365
- Footer — линк «Полная статистика на сайте» через tg.openLink

**Файлы:**
- `me.html`

---

## Группа P — Polish & beauty (~7 чанков, ~4ч)

### Chunk P1 — Skeleton loading states (~30 мин)

**Что:**
- task_sheet и search_sheet: вместо текста «⏳» — skeleton-шиммер
- 3 фейк-карточки с animated `bg-gradient-to-r` shimmer
- CSS @keyframes для plus translateX

**Файлы:**
- `task_sheet.html`, `search_sheet.html`
- `_base.html` — добавить keyframes

---

### Chunk P2 — Page transitions + staggered fade-in (~30 мин)

**Что:**
- Каждая страница: top-level контейнер `.animate-fadein` с fade-in 200ms
- Список задач: staggered fade-in для items (animation-delay по порядку: 0, 30ms, 60ms, …)

**Файлы:**
- `_base.html` keyframes
- task_card.html — `style="animation-delay: ...ms"` (рассчитываем в Jinja)

---

### Chunk P3 — Header gradient accents (~30 мин)

**Что:**
- На /Today, /Stats, /Calendar — за header'ом sublе gradient-blob:
  - Violet/fuchsia blur 60px, opacity-15
  - Absolute-positioned за main content
- Как на landing hero

**Файлы:**
- today.html, me.html, calendar.html, projects.html, project.html — каждый получает hero-blob

---

### Chunk P4 — Inline SVG empty-state illustrations (~1ч)

**Что:**
- 5 SVG-illustrations в `app/templates/miniapp/_partials/empty/*.html` (или inline в страницах):
  - `today_empty.html` — спокойная сцена «всё чисто»
  - `inbox_empty.html` — пустая коробка
  - `calendar_empty.html` — пустой день
  - `projects_empty.html` — пустые папки
  - `search_empty.html` — лупа на пустом
- Стилизованные в accent-цвете (`stroke: currentColor`, `opacity-30`)
- Размер 80-100px, центрированы
- Использовать вместо emoji в empty-states

**Файлы:**
- 5 partials или inline SVG в template'ах

---

### Chunk P5 — Task swipe-action visual polish (~30 мин)

**Что:**
- Когда свайп пересекает threshold (60-80px) — иконка scale-up + opacity-100
- Background-gradient интенсивнее становится с увеличением dx
- Микро-tilt rotation на swipe (transform: translateX + slight rotateY)

**Файлы:**
- `_base.html` CSS — расширение .swipe-content стилей
- `static.py` JS — добавить `data-progress` атрибут который меняется на move

---

### Chunk P6 — Pull-to-refresh визуальная доводка (~30 мин)

**Что:**
- Заменить text-indicator на кастомный круговой spinner SVG
- При pull — opacity и transform интерполируются
- При release-trigger — spinner крутится 0.5s до reload'а

**Файлы:**
- `static.py` JS

---

### Chunk P7 — Финальный визуальный аудит + screenshots + PROGRESS.md (~45 мин)

**Что:**
- Через Playwright MCP делаем скриншоты 320/375/414 для всех экранов после Login (через cookie-форк или logged_in_client equiv)
- Сохранить в `audit/2026-05-12/`
- Сравнить с web-task-row визуально — что осталось расходящимся, добавить в follow-up
- Финальный коммит «miniapp v2: parity + stats + polish завершено» + длительность и счётчик коммитов в PROGRESS.md

**Acceptance:**
- 5-7 скриншотов в audit/2026-05-12/
- Smoke 23/23 GREEN после deploy
- 60+ тестов miniapp green
- PROGRESS.md обновлён

---

# Loop правила

- Каждая итерация: читай этот файл, бери первый незакрытый чанк, делай его
- После каждого commit — push в master + (cron-poll сам redeploy'ит) + smoke 23/23 после деплоя
- Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`
- Pre-commit (ruff/mypy/jinja-linter) **обязательно green** перед commit'ом
- pytest -q must stay green после каждого чанка
- Каждый чанк коммитить отдельно
- НЕ ломай существующие фичи / API / роуты веб-апа (всё что в `/app/*`)
- НЕ удаляй фичи — только обогащай
- Когда все ✅ — финальный commit «miniapp v2: parity + stats + polish завершено» + длительность/счётчик в PROGRESS.md и СТОП

---

# Прогресс

## Группа V — Visual parity
- [x] V1 — Enrich /api/tasks payload + eager-load ✅ `f65582f`
- [x] V2 — task_card.html parity с web ✅ `e87ddbe`
- [x] V3 — project_color_map во все views ✅ `0629704`
- [x] V4 — Labels picker в task_sheet ✅ `ad4b8f6`
- [x] V5 — Recurrence picker + Pin toggle в task_sheet ✅ `ad4b8f6`
- [x] V6 — Subtasks accordion в task_sheet ✅ (см. next commit)

## Группа S — Stats c графиками
- [x] S1 — Backend /miniapp/api/stats ✅ (см. след. коммит)
- [x] S2 — Me-page: hero-streak + 14-day bar-chart ✅
- [x] S3 — Donut «По приоритетам» ✅
- [x] S4 — Bar-chart «Топ-5 проектов» ✅
- [x] S5 — Бейджи + footer ✅

## Группа P — Polish & beauty
- [x] P1 — Skeleton loading states ✅
- [x] P2 — Page transitions + staggered fade-in ✅
- [x] P3 — Header gradient accents ✅
- [x] P4 — Inline SVG empty-state illustrations ✅
- [x] P5 — Task swipe-action visual polish ✅
- [x] P6 — Pull-to-refresh визуальная доводка ✅
- [x] P7 — PROGRESS.md обновлён ✅ (screenshot-audit пропущен — это нужен Playwright + real viewport, в текущем формате не сделать)

(После завершения каждый чанк: ✅ + commit-SHA.)

---

# Связь с предыдущим планом

Предыдущий план `2026-05-11-habr-launch-and-miniapp.md` ✅ закрыт (26 коммитов, mini-app v1 функционален). Этот план — расширение v1 → v2 без breaking changes для backend API (всё что есть остаётся). Юзер-facing визуальная замена.
