# Overnight loop plan — full responsive audit + красивый сайт

**Дата:** 2026-05-10 ночь
**Контекст:** юзер прислал скрин project-view на мобиле (~375px) с 4
видимыми проблемами. Plus просьба «проверка всего адаптива и чтобы
переделалось всё на красивый сайт». Координаты замерены через Playwright.

**Разделено на 3 фазы:** (A) точечные баги со скрина, (B) полный адаптив-
аудит, (C) визуальный полиш.

---

## Фаза A — 4 чанка с конкретного скрина

### Chunk A1 — View-toggle Список/Доска уезжает под sticky topbar (~30 мин)

**Проблема:** на /app/projects/<slug> шапка проекта содержит view-toggle.
При скролле уезжает за topbar (sticky `top-0 h-[62px]`), частично
перекрывается. Видно на скрине — фиолетовая «Список»-плашка бьётся в
нижний край topbar.

**Файлы:** `app/templates/app/project.html`, `app/templates/app/kanban.html`.

**Решение:** блок с view-toggle → `sticky top-[62px]` под topbar с
`bg-[var(--bg)]/95 backdrop-blur` подложкой. ИЛИ если sticky-second-level
ломает kanban-scroll, оставить view-toggle inline и добавить top-padding
к main так чтобы при первом рендере он был ниже topbar.

**Acceptance:** на /app/projects/inbox через Playwright (375px) скролл
вниз 200px — view-toggle либо sticky видим, либо не пересекается с topbar.

---

### Chunk A2 — FAB-кнопки (?-help, search) перекрывают kebab задач (~30 мин)

**Проблема:** fixed-кнопки `?` (y=616) и `🔍` (y=676) часто перекрывают
kebab «⋮» правой колонки task-row (x=302). На скрине видно search-FAB
поверх kebab второй задачи.

**Файлы:** `app/templates/app_base.html` (FAB).

**Решение:** на mobile (`md:hidden`):
1. Сместить FAB `right-3 → right-2`, `w-11 → w-10` (даёт +6px).
2. Увеличить gap между FAB: `bottom-32 → bottom-36` для help.
3. Bottom-padding к content: на mobile `pb-24` чтобы последняя задача не
   зажималась FAB'ом.

Если в шапке задач уже есть kebab (task-list) — рассмотреть скрыть help-FAB
через body-class `data-context="task-list"`.

**Acceptance:** на 375px скрол /app/projects/inbox или /app/today до конца,
kebab последних 2 задач не перекрыт ни search-FAB ни help-FAB.

---

### Chunk A3 — Toolbar «Сортировка / Группа / Выполненные» сжат (~20 мин)

**Проблема:** на скрине три блока в одну строку с тесными иконками. На 320
вероятно overflow.

**Файлы:** `app/templates/app/project.html`.

**Решение:** проверить через Playwright на 320 / 375; добавить `flex-wrap`
+ `gap-1.5 sm:gap-3` + сократить лейблы на mobile («Сорт:» вместо
«Сортировка:», «Гр:» вместо «Группа:»).

**Acceptance:** docW=310 на 320, все три блока видны, не overflow.

---

### Chunk A4 — Lonely kebab у задач без chips (~20 мин)

**Проблема:** task без priority + без даты + без recurrence имеет в action-
area только одинокий «⋮» kebab. Выглядит несбалансированно («💡 Совет: …»
на скрине).

**Файлы:** `app/templates/_partials/task_row.html`.

**Решение:** template-условие — если P4 default, нет due_at, нет recurrence
→ перенести kebab inline в title-row справа от title-button (gap-2),
скрыв пустую action-row. Иначе текущее поведение.

**Acceptance:** task без chips на 375 — kebab привязан к title-row, нет
лишней вертикальной пустоты.

---

## Фаза B — Полный responsive-аудит (5 viewports × 30+ страниц)

### Chunk B1 — Async Playwright скан 320/375/414/768/1280 на 30 страницах

Воссоздать `_seed_for_audit.py` (или использовать существующий
`.tmp_ssh_seed_test_data.py`) для тестового аккаунта `responsive-test@doday.local`.
Залогиниться через Playwright и пройти 5 viewports × 30 страниц:

**Public (8):** landing, pricing, help/index, help/article (3-4 разных slug'а),
privacy, auth/login, auth/register, auth/verify-pending.

**App task-list (12):** today, inbox, upcoming, calendar (month + week),
done, trash, projects/inbox, projects/<custom>, kanban, schedule, habits,
labels.

**App content (10):** stats, activity, profile, graph, projects-archive,
filters, filter (system one), filters/custom (user one), placeholder,
calendar_week.

Для каждой страницы × viewport:
1. Скриншот в `audit/2026-05-10/<page>-<vp>.png`.
2. JS-проверка: `document.scrollWidth` ≤ viewport ширина, нет горизонтального
   скролла, нет overflow culprits с `el.right > vw + 1`.
3. Запись результата в `audit/2026-05-10/scan-results.json` с list of issues.

**Acceptance:** все 150 (30×5) проверок документированы в JSON. Зеро- или
малое-число фейлов. Каждый найденный фейл занесён в `audit/2026-05-10/issues.md`
с координатами и предлагаемым фиксом.

### Chunk B2 — Фикс всех найденных issues

Пройтись по `audit/2026-05-10/issues.md` и закрыть каждый. После каждых
3-5 фиксов — commit + push + redeploy + re-scan тех же страниц. Цель —
0 culprits на всех 5 viewports.

**Acceptance:** повторный скан показывает 0 horizontal-overflow на всех
комбинациях viewport × page.

---

## Фаза C — Visual polish («красивый сайт»)

### Chunk C1 — Typography passes (~1 час)

- Проверить line-height / letter-spacing для headings (`h1/h2/h3`) — не
  слишком тесно, не слишком широко
- Body-text: `leading-relaxed` (1.625) для длинных текстов (help-articles,
  privacy)
- Mobile font-sizes: убедиться что текст не мельче 14px на mobile (12px
  только для мелких бейджей)
- `tabular-nums` для всех числовых значений (счётчики, даты в task-row)

### Chunk C2 — Spacing & rhythm passes (~1 час)

- Card padding: проверить consistency `p-4`/`p-5`/`p-6` — должно быть
  одно правило (например `p-4 sm:p-5 lg:p-6`)
- Section gaps между виджетами на /today (morning_briefing, daily_goal,
  mood, week_plan, today_schedule, sprint, retro, school_streak,
  school_holiday, daily_note, completed_today, countdown_pins) — должны
  быть равны (например `space-y-4 sm:space-y-5`)
- Onboarding-card на новых юзеров — отступы вокруг
- Sidebar items vertical rhythm

### Chunk C3 — Subtle animations & polish (~1 час)

- Hover-transitions: убедиться что у всех clickable элементов есть
  `transition` хотя бы 150ms
- Focus rings: всё что фокусится с клавиатуры должно иметь видимый ring
  (accessibility + красота)
- Loading states: HTMX swaps — добавить `htmx-indicator` SVG-spinner
  если ещё нет
- Empty states: проверить что когда экран пустой (Inbox без задач,
  /app/done без выполненных, /app/trash пустой), есть приятная иллюстрация
  + CTA
- Confirmations: удаление задачи / проекта — есть ли `confirm()` или
  inline undo?

### Chunk C4 — Color & contrast passes (~30 мин)

- Audit color contrast: text vs background минимум WCAG AA (4.5:1 для
  body, 3:1 для large)
- Dark theme: проверить что не «серая каша» — есть accent contrast
- Light theme (если есть): тоже работает
- Status colors: error/success/warning имеют достаточный контраст

### Chunk C5 — Micro-UX (~1 час)

- Все кнопки имеют title/aria-label для screen-readers
- Touch-targets везде ≥36px (audit pass — может быть найдены пропуски)
- Skip-to-content link для скрин-ридеров
- Keyboard navigation: tab-order разумный, no tab-traps
- Form validation: ошибки рядом с полями, не модалкой
- 404-страница: красивая, с CTA «вернуться домой»

---

## Loop правила

- Каждая итерация: читай этот файл, бери первый незакрытый чанк, делай его.
- После каждого commit — push в master + redeploy `.tmp_ssh_inspect.py` +
  smoke 18/18 (часть acceptance).
- Russian past-tense commits, author
  `112168281+SwairIt@users.noreply.github.com`.
- Pre-commit (ruff/mypy/jinja-linter) **обязательно green** перед commit'ом.
- После каждого фикса — Playwright проверь 320/375 что улучшение видно и
  что не сломал то что уже работает.
- **Каждый чанк коммитить отдельно** — в т.ч. под-итерации фазы C.
- Чанки B2 и фазы C — итеративные. Можешь делать несколько проходов.
  После каждых 3-5 фиксов — отдельный commit.
- НЕ трогай архитектуру / API. Только template/CSS/визуал.
- НЕ удаляй фичи. Только улучшай как они выглядят.
- Когда фаза A полностью ✅ — переходи к B. Когда B ✅ — переходи к C.
- Когда все ✅ — финальный commit «overnight: full responsive + polish
  завершено» + длительность/счётчик в PROGRESS.md и СТОП.

## Прогресс

### Фаза A — Точечные баги со скрина юзера
- [x] A1 — View-toggle Список/Доска под sticky topbar ✅
- [x] A2 — FAB-кнопки не перекрывают kebab ✅
- [ ] A3 — Toolbar Сортировка/Группа на мобиле
- [ ] A4 — Lonely kebab без chips

### Фаза B — Полный responsive-аудит
- [ ] B1 — Async Playwright скан 320/375/414/768/1280 × 30 страниц + JSON-отчёт
- [ ] B2 — Закрытие всех найденных issues (итеративно)

### Фаза C — Visual polish
- [ ] C1 — Typography passes
- [ ] C2 — Spacing & rhythm
- [ ] C3 — Animations & polish details
- [ ] C4 — Color & contrast
- [ ] C5 — Micro-UX (a11y, touch-targets, keyboard nav, forms, 404)

(После завершения каждый чанк: ✅ + commit-SHA.)
