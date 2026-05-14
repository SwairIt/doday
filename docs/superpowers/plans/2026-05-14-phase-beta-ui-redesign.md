# Phase β — UI redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Упростить UI веб-апа и Mini App — slim sidebar, single-line task row, единый settings-экран, Mini App на light-theme по умолчанию + упрощённые chips. Спецификация — `docs/superpowers/specs/2026-05-13-doday-simplify-and-teams-design.md`, секция «Phase β».

**Architecture:** 5 атомных tasks, каждый = отдельный commit. Web light-theme default и 1-экранный onboarding **уже сделаны** (α follow-up + текущее состояние) — поэтому β скромнее изначального scope. Pre-commit (ruff + mypy strict + jinja-linter) green + pytest без новых падений после каждого task. Push + smoke в финальном task.

**Tech Stack:** FastAPI + Jinja2 + HTMX 2 + Alpine.js + Tailwind CDN. Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`.

---

## Current state (recon 2026-05-14)

- **Web theme:** `:root` в `base.html:179-197` = LIGHT values. `[data-theme="dark"]` = override. Anti-flash script `base.html:144-176` читает `localStorage['doday-theme']`, fallback `'system'`. **Light уже default — не трогаем.**
- **Web sidebar** `app/templates/_partials/sidebar.html` (231 строк): 9 main nav items (inbox/today/upcoming/calendar/stats/done/labels/activity/trash) + 4 filters + favorites + projects + mini-calendar + admin + footer.
- **Web task row** `app/templates/_partials/task_row.html` (341 строк): bulk-checkbox, caret, toggle, pin, project-dot, title, description, stale-badge, labels, subtask-progress, priority-chip, recurrence-chip, due-chip, mobile-kebab, desktop hover-strip (6 кнопок).
- **Profile** `app/templates/app/profile.html` (767 строк): 9 секций. Route `GET /app/profile` в `app/views/router.py:584`. Нет `/app/settings`.
- **Onboarding:** нет wizard. `_partials/onboarding_card.html` — 1 dismissable card в `today.html:31`. **Уже простой — не трогаем.**
- **Mini App theme:** default DARK. Anti-flash `miniapp/_base.html:14-24` читает `localStorage['dodayTheme']`, fallback `'dark'`. `static.py` `currentSaved()` fallback `'dark'`. `[data-theme="light"]` блок уже есть в `_base.html:63-79`.
- **Mini App task_card** `app/templates/miniapp/_partials/task_card.html` (163 строк): drag-handle, toggle, pomodoro-btn, pin, project-dot, title, description, labels, subtask-progress, stale-badge, chips-strip (priority + due + recurrence).

---

## File Structure

```
MODIFY:
app/templates/miniapp/_base.html                  β1: anti-flash default 'dark' → 'light'
app/miniapp/static.py                             β1: currentSaved() fallback 'dark' → 'light'
app/templates/_partials/sidebar.html              β2: 9 nav → 5; перенос stats/done/labels/activity/trash
app/templates/_partials/task_row.html             β3: 3-row layout → single-line; chips в overflow
app/templates/miniapp/_partials/task_card.html     β4: убрать stale-badge/subtask-progress из строки
app/views/router.py                               β5: /app/settings route + /app/profile redirect
CREATE:
app/templates/app/settings.html                   β5: единый settings-экран

TESTS (modify as needed):
tests/test_miniapp_pages.py                        β1: theme-default assertions
tests/test_sidebar.py (if exists)                  β2: nav item count
tests/test_task_row.py / test_task_keyboard.py     β3: structure assertions
tests/test_settings.py (create)                    β5: /app/settings renders
```

---

## Task 1: Mini App — light theme default

**Files:**
- Modify: `app/templates/miniapp/_base.html:14-24` (anti-flash script)
- Modify: `app/miniapp/static.py` (`currentSaved()` function)
- Modify: `tests/test_miniapp_pages.py` (theme assertion if any)

- [ ] **Step 1: Change anti-flash script default in `_base.html`**

Open `app/templates/miniapp/_base.html`, lines 14-24. Current:

```javascript
(function () {
  try {
    var t = localStorage.getItem('dodayTheme') || 'dark';
    var eff = (t === 'system') ? 'dark' : t;
    document.documentElement.setAttribute('data-theme', eff);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
```

Replace with (default `'light'`, `'system'` resolves via matchMedia):

```javascript
(function () {
  try {
    var t = localStorage.getItem('dodayTheme') || 'light';
    var eff = t;
    if (t === 'system') {
      eff = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', eff);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
```

- [ ] **Step 2: Change `currentSaved()` fallback in `static.py`**

Open `app/miniapp/static.py`, find function `currentSaved()` inside the `MINIAPP_JS` string (around line 49-51):

```javascript
function currentSaved() {
  try { return localStorage.getItem('dodayTheme') || 'dark'; } catch (e) { return 'dark'; }
}
```

Replace both `'dark'` fallbacks with `'light'`:

```javascript
function currentSaved() {
  try { return localStorage.getItem('dodayTheme') || 'light'; } catch (e) { return 'light'; }
}
```

Also check `resolveTheme()` in the same file — it has `return (tg.colorScheme === 'light') ? 'light' : 'dark';` for the `'system'` case. That's fine, leave it (system follows Telegram's colorScheme).

- [ ] **Step 3: Update test if it asserts dark-default**

```bash
grep -rn "dodayTheme\|data-theme\|'dark'\|\"dark\"" tests/test_miniapp_pages.py
```

If a test asserts the default is dark, update it to light. If no such test — skip.

- [ ] **Step 4: pre-commit**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
```
Expected: green.

- [ ] **Step 5: pytest**

```bash
uv run pytest -q tests/test_miniapp_pages.py 2>&1 | tail -10
```
ConnectionRefusedError accepted (infra). No new logic failures.

- [ ] **Step 6: Commit**

```bash
git add app/templates/miniapp/_base.html app/miniapp/static.py tests/test_miniapp_pages.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(β): Mini App — light theme по умолчанию

Anti-flash script + currentSaved() fallback переключены с 'dark' на
'light'. 'system' теперь резолвится через prefers-color-scheme.
Согласовано с web-апом, где light уже default. Тёмная — через
переключатель на /miniapp/me, сохраняется в localStorage.
EOF
)"
```

---

## Task 2: Web sidebar — slim 9 nav items → 5

**Files:**
- Modify: `app/templates/_partials/sidebar.html`

Goal: главный nav = **Inbox, Сегодня, Ближайшие, Календарь, Проекты**. Переместить `Статистика / Завершённые / Лейблы / Активность / Корзина` в компактную «ещё» секцию (collapsible `<details>`) внизу, перед footer.

- [ ] **Step 1: Read current sidebar structure**

```bash
sed -n '1,60p' app/templates/_partials/sidebar.html
```

Identify the main-nav list (lines ~21-31 per recon) — a hardcoded list of nav items.

- [ ] **Step 2: Split nav items into primary + secondary**

In `app/templates/_partials/sidebar.html`, find the main nav loop/list. Primary 4 items (keep at top, the existing markup): `inbox`, `today`, `upcoming`, `calendar`. (Проекты-секция already exists separately below — leave it.)

Secondary items to move into a collapsible block: `stats`, `done`, `labels`, `activity`, `trash`.

Replace the secondary items' rendering with a `<details>` element placed just **above the footer** (before line ~147):

```html
{# Вторичная навигация — спрятана под «Ещё» чтобы sidebar был чище #}
<details class="mt-2 px-3 group">
  <summary class="flex items-center gap-2 py-1.5 text-sm text-[var(--text-muted)] cursor-pointer select-none list-none">
    <svg class="w-4 h-4 transition group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
    Ещё
  </summary>
  <div class="mt-1 space-y-0.5">
    <a href="/app/stats" class="sidebar-link {% if current_path == '/app/stats' %}active{% endif %}">📊 Статистика</a>
    <a href="/app/done" class="sidebar-link {% if current_path == '/app/done' %}active{% endif %}">✓ Завершённые</a>
    <a href="/app/labels" class="sidebar-link {% if current_path == '/app/labels' %}active{% endif %}">🏷 Лейблы</a>
    <a href="/app/activity" class="sidebar-link {% if current_path == '/app/activity' %}active{% endif %}">📈 Активность</a>
    <a href="/app/trash" class="sidebar-link {% if current_path == '/app/trash' %}active{% endif %}">🗑 Корзина</a>
  </div>
</details>
```

**IMPORTANT:** Match the existing CSS class names. If the sidebar uses a class like `nav-item` or similar instead of `sidebar-link`, use that. Read the existing item markup first and copy its exact class structure. The `📊/✓/🏷/📈/🗑` emoji should match whatever icon approach the existing items use (if they use inline SVG, replicate that pattern instead of emoji).

If the existing items render via a `{% for %}` loop over a Python-provided list, instead split the list: primary items render in the loop, secondary items go in the `<details>`. Adjust to match the actual structure you see.

- [ ] **Step 2b: Preserve badge counts**

The recon noted badge counts for `inbox`, `today`, `upcoming`, `trash`. Primary items keep their badges. For `trash` (now in «Ещё») — keep its badge too if the markup supports it; if too fiddly, dropping the trash-badge is acceptable (note it in report).

- [ ] **Step 3: jinja-linter**

```bash
uv run python scripts/lint_templates.py app/templates/_partials/sidebar.html 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 4: pre-commit + pytest**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q 2>&1 | tail -10
```
Pre-commit green. pytest — no new failures (ConnectionRefused accepted).

- [ ] **Step 5: Commit**

```bash
git add app/templates/_partials/sidebar.html
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(β): slim sidebar — 5 главных пунктов, остальное под «Ещё»

Главная навигация: Inbox / Сегодня / Ближайшие / Календарь + проекты.
Статистика, Завершённые, Лейблы, Активность, Корзина убраны под
collapsible «Ещё» над футером. Badge-счётчики на главных пунктах
сохранены.
EOF
)"
```

---

## Task 3: Web task row — single-line layout

**Files:**
- Modify: `app/templates/_partials/task_row.html`

Goal: задача рендерится в **одну строку** на desktop. Структура:
```
○  Заголовок — лейбл              дата    ⋯
```
- `○` — toggle-circle (priority-colored border) — KEEP as is
- Title — KEEP, single line, truncate
- ` — лейбл` — первый лейбл, italic-muted, только если есть. Без `@`-префикса.
- Дата — compact, справа
- `⋯` — overflow button, открывает context-menu / detail panel

**Скрыть из строки** (видны в detail-panel, который открывается по клику): description preview, stale-badge «Висит N дн.», subtask-progress chip, recurrence chip, multi-label chips, desktop hover-strip с 6 кнопками.

**KEEP working:** bulk-select checkbox (mobile + hover), subtask-expand caret, complete-toggle, click-to-open-detail.

- [ ] **Step 1: Read full current task_row.html**

```bash
cat app/templates/_partials/task_row.html
```

Map out each element block (recon gave line ranges, but verify against actual file).

- [ ] **Step 2: Rewrite the row markup**

This is the biggest edit in β. Preserve:
- The outer `div#task-wrap-{id}` wrapper + the two hidden slots (`#subtasks-of-{id}-slot`, `#comments-slot-{id}`) — HTMX targets depend on them.
- Bulk-select checkbox block.
- Subtask-expand caret block.
- Complete-toggle circle block.
- The title button (HTMX click → detail panel, dblclick → edit).
- `data-*` attributes on the row (priority, project, etc.) — other JS reads them.

Change:
- Wrap into a single flex row `flex items-center gap-2` — NO `flex-wrap`, NO multi-row mobile layout.
- After title, add: ` {% if task.labels %}<span class="text-xs text-[var(--text-muted)] italic truncate">— {{ task.labels[0].name }}</span>{% endif %}` — only the FIRST label, no `@`.
- Keep the due-date chip but simplified — just the date text, `text-xs`, no popover inline (popover moves to overflow menu). Actually: KEEP the existing due-date popover button as-is if removing it is risky — just ensure it doesn't wrap. The priority is single-line; if the due-popover fits on one line, keep it.
- Remove from the row's always-visible markup: description preview block, stale-badge block, subtask-progress chip block, recurrence chip block, the extra label chips (keep only first-label inline text from above).
- Replace the desktop hover action-strip (6 buttons) + mobile kebab with a SINGLE `⋯` overflow button that dispatches the existing `contextmenu` event (the recon noted mobile-kebab already does `dispatches contextmenu event to reuse the context-menu partial` — make the `⋯` button do that for all viewports).

**If the rewrite risks breaking HTMX wiring** — proceed carefully, keep every `hx-*` attribute and every `id` intact. The visual simplification is about hiding/removing chip markup, not about changing the HTMX contract.

- [ ] **Step 3: Verify HTMX targets still exist**

```bash
grep -nE "id=\"(task-wrap|subtasks-of|comments-slot)" app/templates/_partials/task_row.html
grep -nE "hx-(get|post|delete|target|swap)" app/templates/_partials/task_row.html | head -20
```
All HTMX wiring that was there before must still be there (just possibly moved into the overflow menu / detail panel trigger).

- [ ] **Step 4: jinja-linter + pre-commit**

```bash
uv run python scripts/lint_templates.py app/templates/_partials/task_row.html 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -10
```
Both green.

- [ ] **Step 5: pytest**

```bash
uv run pytest -q 2>&1 | tail -15
```
Pay attention to `tests/test_task_row.py`, `tests/test_task_keyboard.py`, `tests/test_task_detail.py` if they exist — they may assert on specific markup. If a test asserts presence of e.g. the stale-badge in the row, update the test to reflect that it moved to the detail panel (or remove that assertion). ConnectionRefused errors accepted.

- [ ] **Step 6: Commit**

```bash
git add app/templates/_partials/task_row.html tests/
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(β): task row в одну строку — убрал chip-перегруз

Строка задачи теперь: toggle ○ + заголовок + первый лейбл (italic) +
дата + overflow ⋯. Убрано из строки (видно в detail-панели по клику):
description preview, «висит N дн.», subtask-progress, recurrence-chip,
мульти-лейбл chips, desktop hover-strip из 6 кнопок → один ⋯.

HTMX-обвязка (task-wrap, subtasks-of, comments-slot слоты, hx-*
атрибуты) сохранена без изменений.
EOF
)"
```

---

## Task 4: Mini App task_card — simplify chips

**Files:**
- Modify: `app/templates/miniapp/_partials/task_card.html`

Goal: убрать из карточки то что перегружает — синхронно с web task_row.

**Убрать** (видно в task_sheet по тапу):
- stale-badge «Висит N дн.» (lines ~113-126)
- subtask-progress chip (lines ~92-111)
- description preview (lines ~79-81) — оставить? На мобиле 1-line clamp полезен. **Решение: оставить description (1-line) но убрать stale-badge и subtask-progress.**

**Оставить:** drag-handle, toggle, pomodoro-btn, pin, project-dot, title, первый лейбл, chips-strip (priority + due + recurrence).

**Лейблы:** сейчас все лейблы как chips (lines ~83-90). Оставить только первый — как `— labelname` italic, согласно web.

- [ ] **Step 1: Read task_card.html**

```bash
cat app/templates/miniapp/_partials/task_card.html
```

- [ ] **Step 2: Remove stale-badge + subtask-progress blocks**

Delete the `«Висит N дн.»` Alpine block (~lines 113-126) and the subtask-progress chip block (~lines 92-111).

- [ ] **Step 3: Collapse label chips to first-label inline**

Replace the multi-label chips loop (~lines 83-90) with a single inline:

```html
{% if task.labels %}
  <span class="text-[10px] text-[var(--text-muted)] italic ml-1">— {{ task.labels[0].name }}</span>
{% endif %}
```

Place it right after the title span. Match surrounding indentation/structure.

- [ ] **Step 4: jinja-linter + pre-commit**

```bash
uv run python scripts/lint_templates.py app/templates/miniapp/_partials/task_card.html 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -10
```
Both green.

- [ ] **Step 5: pytest**

```bash
uv run pytest -q tests/test_miniapp_pages.py 2>&1 | tail -10
```
No new failures.

- [ ] **Step 6: Commit**

```bash
git add app/templates/miniapp/_partials/task_card.html
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(β): Mini App task_card — упростил chips

Убрал из карточки: «висит N дн.» badge, subtask-progress chip,
мульти-лейбл chips → один первый лейбл inline italic. Осталось:
toggle, pomodoro, pin, project-dot, title, description (1 строка),
chips-strip (priority + due + recurrence). Синхронно с web task_row.
EOF
)"
```

---

## Task 5: `/app/settings` — единый settings-экран

**Files:**
- Create: `app/templates/app/settings.html`
- Modify: `app/views/router.py` (add `/app/settings` route, redirect `/app/profile` → `/app/settings`)

Goal: один скролл-экран settings вместо разбросанной 767-строчной profile.html. Профиль становится одной из секций.

**Подход (минимально-рискованный):** НЕ переписываем всю profile.html с нуля. Вместо этого:
1. Создаём `/app/settings` route который рендерит **новый** `settings.html`.
2. `settings.html` extends `app/base.html`, содержит секции в порядке: Профиль → Внешний вид → Уведомления → Школьный дневник → Безопасность → Опасная зона. Каждая секция — **переиспользует существующую разметку** из profile.html (копируем блоки as-is, profile.html уже почищен от achievements/audience в α).
3. `/app/profile` route — оставляем, но он `RedirectResponse('/app/settings', 303)`.
4. Старый `profile.html` можно оставить в репе неиспользуемым ИЛИ удалить. **Решение: удалить `profile.html` после переноса** — не держим dead-код.

Фактически settings.html ≈ profile.html с другим заголовком и (опционально) реорганизованным порядком. Это «переименование + redirect», не полная переделка. Изначальный β-замысел «один экран» — profile.html УЖЕ один экран (767 строк скролла, не табы). Так что основная задача — **route consistency** (`/app/settings` как канон) + чистка.

- [ ] **Step 1: Read current profile route + template**

```bash
sed -n '584,632p' app/views/router.py
wc -l app/templates/app/profile.html
```

- [ ] **Step 2: Create `app/templates/app/settings.html`**

Copy `app/templates/app/profile.html` content into `app/templates/app/settings.html`. Change:
- `{% block title %}` → `Настройки — Doday`
- Page `<h1>` → `Настройки`
- Keep all sections as-is (they already work).

```bash
cp app/templates/app/profile.html app/templates/app/settings.html
```
Then Edit `settings.html` to fix title + h1.

- [ ] **Step 3: Add `/app/settings` route in `app/views/router.py`**

Find the existing `/app/profile` handler (line ~584). Duplicate it as `/app/settings` rendering `settings.html` with the SAME context dict. Then change the `/app/profile` handler body to:

```python
from fastapi.responses import RedirectResponse

@router.get("/app/profile")
async def profile_redirect() -> RedirectResponse:
    return RedirectResponse("/app/settings", status_code=303)
```

(Keep the real logic in the `/app/settings` handler.)

**IMPORTANT:** look at the actual handler signature first — it has dependencies (`RequiredUser`, `DbSession`, etc.) and builds a context dict. The `/app/settings` handler keeps ALL of that. Only `/app/profile` becomes a thin redirect.

- [ ] **Step 4: Update sidebar footer link**

`app/templates/_partials/sidebar.html` footer links to `/app/profile`. Change it to `/app/settings` (the redirect would work anyway, but direct link avoids a 303 hop).

```bash
grep -n "/app/profile" app/templates/_partials/sidebar.html
```

- [ ] **Step 5: Delete the old profile.html**

```bash
rm app/templates/app/profile.html
```

Verify nothing else references `profile.html`:
```bash
grep -rn "profile.html" app/ --include="*.py" 2>&1
```
If the `/app/profile` redirect handler still references `profile.html` — fix it (it shouldn't, it's a pure redirect now).

- [ ] **Step 6: Create `tests/test_settings.py`**

```python
"""Tests for the unified /app/settings screen."""

from httpx import AsyncClient


async def test_settings_page_renders(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/app/settings")
    assert r.status_code == 200
    assert "Настройки" in r.text


async def test_profile_redirects_to_settings(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/app/profile", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/settings"


async def test_settings_unauth_redirects(client: AsyncClient) -> None:
    r = await client.get("/app/settings", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
```

- [ ] **Step 7: jinja-linter + pre-commit**

```bash
uv run python scripts/lint_templates.py 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -10
```
Both green.

- [ ] **Step 8: pytest**

```bash
uv run pytest -q tests/test_settings.py 2>&1 | tail -10
```
If local Postgres is up — should pass. If down (ConnectionRefused) — at least no import/collection errors.

Also check `tests/test_profile*.py` if exists — update any test that GETs `/app/profile` and expects 200 to expect 303, or to GET `/app/settings`.

- [ ] **Step 9: Commit**

```bash
git add app/templates/app/settings.html app/views/router.py app/templates/_partials/sidebar.html tests/test_settings.py
git rm app/templates/app/profile.html
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(β): /app/settings — единый экран настроек

profile.html → settings.html (заголовок «Настройки»). Секции:
Профиль / Внешний вид / Уведомления / Школьный дневник / Безопасность
/ Опасная зона. /app/profile теперь 303-редирект на /app/settings.
Sidebar-футер ссылается напрямую на /app/settings. Старый profile.html
удалён — не держим dead-код.
EOF
)"
```

---

## Task 6: Push + deploy + smoke

**Files:** —

- [ ] **Step 1: Sanity check commits**

```bash
git log --oneline -8 2>&1
```
Expected: 5 β-commits (Tasks 1-5) on top of `63978a4`.

- [ ] **Step 2: Push**

```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master 2>&1 | tail -3
```

- [ ] **Step 3: Wait deploy + verify prod HEAD matches local**

```bash
until curl -fsS https://getdoday.ru/health 2>/dev/null | grep -q "ok"; do sleep 5; done
```
Then SSH-check prod `git rev-parse HEAD` matches local HEAD (poll up to 5 min).

- [ ] **Step 4: Smoke 23/23**

```bash
uv run python scripts/smoke_test.py https://getdoday.ru 2>&1 | tail -10
```
Expected: `all 23 green`.

- [ ] **Step 5: Manual page checks**

```bash
for path in /app/today /app/settings /app/profile /miniapp/ ; do
  curl -s -o /dev/null -w "%{http_code} $path\n" https://getdoday.ru$path
done
```
Expected: `/app/today` 200 (or 302→login if unauth), `/app/settings` 302/200, `/app/profile` 303, `/miniapp/` 303.

- [ ] **Step 6: Update PROGRESS.md**

Prepend entry:
```markdown
## 2026-05-14 — Phase β: UI redesign завершён

Mini App переведён на light-theme по умолчанию. Web sidebar урезан с
9 пунктов до 5 главных + «Ещё» collapsible. Task row (web) — одна
строка вместо трёх, chip-перегруз убран в detail-панель. Mini App
task_card упрощён синхронно. /app/settings — единый экран настроек,
/app/profile редиректит на него, старый profile.html удалён.

Smoke 23/23 GREEN. Next: Phase γ — comments UI polish.
```

Commit:
```bash
git add PROGRESS.md
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "docs(β): PROGRESS обновлён — UI redesign завершён"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master 2>&1 | tail -3
```

- [ ] **Step 7: Report**

Push output, prod HEAD match, smoke result, page checks, any concerns.

---

## Self-Review (выполнено)

**Spec coverage:**
- β light theme default — web УЖЕ done (recon confirmed), Mini App = Task 1 ✓
- β sidebar slim — Task 2 ✓
- β task row single-line — Task 3 ✓
- β Mini App task_card simplify — Task 4 ✓
- β settings один экран — Task 5 ✓
- β welcome 1-step — УЖЕ done (onboarding_card, recon confirmed) — no task needed ✓
- β landing/pricing copy — УЖЕ done в α follow-up ✓

**Placeholder scan:** нет TBD. Каждый task имеет точные file:line + exact commands. Task 2/3 содержат «match existing structure» guidance т.к. точная разметка зависит от runtime — implementer читает файл первым шагом.

**Type/name consistency:** `localStorage['dodayTheme']` (Mini App, camelCase) vs `localStorage['doday-theme']` (web, kebab) — намеренно разные, recon это подтвердил, не путаем. `/app/settings` имя консистентно во всех tasks.

**Scope check:** 6 tasks, последовательны, каждый atomic. Task 3 (task row) — самый рискованный (HTMX wiring), implementer проинструктирован сохранять все `hx-*` + `id`.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-14-phase-beta-ui-redesign.md`. Continue with **subagent-driven-development** (same as Phase α).
