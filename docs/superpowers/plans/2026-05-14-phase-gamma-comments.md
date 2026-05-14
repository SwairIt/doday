# Phase γ — Comments UI polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Добавить comments-секцию в Mini App task_sheet (на web comments уже работают), и закрыть β3-concern — context-menu получает labels + comments actions, hover-strip из task_row убирается.

**Architecture:** 3 атомных tasks. Backend `app/comments/` полностью готов (4 endpoints, cookie-auth работает и для web и для Mini App). Web task-detail уже рендерит comments (`task_detail.html:386` + `comments_block.html`) — **не трогаем**. Pre-commit green + pytest без новых падений после каждого task.

**Tech Stack:** FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CDN. Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`.

---

## Current state (recon 2026-05-14)

- **Backend:** `task_comments_router` (`GET`/`POST /api/tasks/{id}/comments`) + `comments_router` (`PATCH`/`DELETE /api/comments/{id}`). `CommentOut`: `{id, task_id, body, created_at, updated_at}`. Auth `RequiredUser` + ownership. Mini App ставит cookie через `attemptAuth()` — эти web-endpoints для неё доступны.
- **Web:** `task_detail.html:386-418` уже имеет comments-секцию (list + delete + add-form, HTMX). Работает. **Не трогаем.**
- **Mini App `task_sheet.html`** (528 строк): 10 секций (title/priority/due/project/labels/recurrence/reminders/pomodoro/subtasks/actions). **Нет comments.** Alpine state `dodayTaskSheet()` (script ~line 263) — нет comment-методов. `loadTask()` fetch'ит `/miniapp/api/tasks/{id}`.
- **Context-menu `task_context_menu.html`:** actions через `data-ctx="..."`, vanilla-JS handler (`menu.addEventListener('click')` ~line 154). Есть: detail/edit/duplicate/prio-1..4/due-*/snooze-*/due-clear/pin/move/delete. **Нет `labels`, нет `comments`.**
- **Task row `task_row.html`:** после β3 — desktop hover-strip из 3 кнопок (labels-popover, comments-toggle, delete) на `lg:group-hover`. labels/comments туда попали т.к. их не было в context-menu.

---

## File Structure

```
MODIFY:
app/templates/miniapp/_partials/task_sheet.html    γ1: + comments accordion + Alpine методы
app/templates/_partials/task_context_menu.html     γ2: + data-ctx="labels" + data-ctx="comments" + JS handler
app/templates/_partials/task_row.html              γ2: убрать hover-strip (3 кнопки) — всё в ⋯ context-menu
tests/test_miniapp_pages.py                        γ1: assertion comments-секции
tests/test_comments.py / test_polish_batch_2.py    γ2: context-menu actions (если есть assertions на hover-strip)
```

---

## Task 1: Mini App task_sheet — comments accordion

**Files:**
- Modify: `app/templates/miniapp/_partials/task_sheet.html`
- Modify: `tests/test_miniapp_pages.py`

- [ ] **Step 1: Read the file**

```bash
cat app/templates/miniapp/_partials/task_sheet.html
```
Note exactly:
- Where the subtasks accordion section ends (~line 220) — comments go right after it, before the actions row (~line 222).
- The structure of the existing accordions (pomodoro ~149-181, subtasks ~183-220) — match their markup pattern (the `<details>` or Alpine `x-show` toggle style they use).
- The `dodayTaskSheet()` Alpine state object (~line 263+) — note where `loadTask`, `loadSubtasks` etc. are defined, and the `task` / current-task-id reference (`this.task.id` or similar).

- [ ] **Step 2: Add the comments section markup**

Insert AFTER the subtasks accordion, BEFORE the actions row. Match the existing accordion style. Template:

```html
{# Comments accordion (γ) — lazy-fetch при первом раскрытии #}
<div>
  <button type="button" @click="commentsOpen = !commentsOpen; if (commentsOpen && comments === null) loadComments()"
          class="w-full flex items-center justify-between py-2 text-sm font-medium text-[var(--text)]">
    <span>💬 Комментарии<span x-show="comments && comments.length" x-cloak class="text-[var(--text-muted)]" x-text="' · ' + (comments ? comments.length : '')"></span></span>
    <svg class="w-4 h-4 transition text-[var(--text-muted)]" :class="commentsOpen ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
  </button>
  <div x-show="commentsOpen" x-cloak class="space-y-2 pt-1">
    <template x-if="comments === null">
      <p class="text-xs text-[var(--text-muted)] py-2">Загрузка…</p>
    </template>
    <template x-if="comments && comments.length === 0">
      <p class="text-xs text-[var(--text-muted)] py-2">Пока нет комментариев</p>
    </template>
    <template x-for="c in (comments || [])" :key="c.id">
      <div class="rounded-lg bg-[var(--surface-2)] px-3 py-2">
        <p class="text-sm whitespace-pre-wrap break-words" x-text="c.body"></p>
        <div class="flex items-center justify-between mt-1">
          <span class="text-[10px] text-[var(--text-muted)]" x-text="formatCommentDate(c.created_at)"></span>
          <button type="button" @click="deleteComment(c.id)"
                  class="text-[10px] text-[var(--text-muted)] hover:text-rose-400 transition">удалить</button>
        </div>
      </div>
    </template>
    <div class="flex items-end gap-2 pt-1">
      <textarea x-model="newComment" rows="2" placeholder="Написать комментарий…"
                class="flex-1 text-sm rounded-lg bg-[var(--surface-2)] border border-[var(--border)] px-3 py-2 resize-none focus:outline-none focus:border-[var(--accent)]"></textarea>
      <button type="button" @click="addComment()" :disabled="!newComment.trim()"
              class="shrink-0 px-3 py-2 rounded-lg bg-[var(--accent)] text-[var(--tg-button-text)] text-sm font-medium disabled:opacity-40 transition">➤</button>
    </div>
  </div>
</div>
```

**IMPORTANT:** if the existing accordions use `<details>`/`<summary>` instead of the Alpine `x-show` toggle shown above — match THAT pattern instead. Read the pomodoro/subtasks sections first and replicate their exact structure (class names, toggle mechanism). The markup above is the intent; the form must match house style.

- [ ] **Step 3: Add Alpine state + methods to `dodayTaskSheet()`**

In the `dodayTaskSheet()` object (script ~line 263+):

Add to the state object (near `subtasks: []` etc.):
```javascript
comments: null,
commentsOpen: false,
newComment: '',
```

Add these methods (near `loadSubtasks` / `addSubtask`):
```javascript
formatCommentDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch (e) { return ''; }
},
async loadComments() {
  if (!this.task || !this.task.id) return;
  try {
    const r = await fetch('/api/tasks/' + this.task.id + '/comments', { credentials: 'include' });
    this.comments = r.ok ? await r.json() : [];
  } catch (e) { this.comments = []; }
},
async addComment() {
  const body = this.newComment.trim();
  if (!body || !this.task || !this.task.id) return;
  try {
    const r = await fetch('/api/tasks/' + this.task.id + '/comments', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body }),
    });
    if (r.ok) { this.newComment = ''; await this.loadComments(); }
  } catch (e) {}
},
async deleteComment(id) {
  try {
    await fetch('/api/comments/' + id, { method: 'DELETE', credentials: 'include' });
    await this.loadComments();
  } catch (e) {}
},
```

**IMPORTANT:** match the actual reference used for the current task in the existing methods. If `loadSubtasks` uses `this.task.id` — use that. If it uses a different var (e.g. `this.taskId` or `this.currentId`) — use the same. Read an existing method first.

Also: when the sheet closes/reopens for a different task, `comments` must reset. Find where `loadTask()` resets state (it likely resets `subtasks`, `reminders` etc.) and add `this.comments = null; this.commentsOpen = false; this.newComment = '';` there.

- [ ] **Step 4: jinja-linter**

```bash
uv run python scripts/lint_templates.py app/templates/miniapp/_partials/task_sheet.html 2>&1 | tail -5
```
0 errors.

- [ ] **Step 5: Add test assertion**

In `tests/test_miniapp_pages.py`, find a test that GETs a miniapp page and checks rendered content. Add an assertion (or a small new test) that the task_sheet partial includes the comments section. Since task_sheet is included in miniapp pages, a simple check:

```python
async def test_miniapp_task_sheet_has_comments_section(logged_in_client: AsyncClient) -> None:
    """γ: task_sheet включает секцию комментариев."""
    r = await logged_in_client.get("/miniapp/")
    assert r.status_code == 200
    assert "loadComments" in r.text
    assert "Комментарии" in r.text
```

- [ ] **Step 6: pre-commit + pytest**

```bash
uv run pre-commit run --all-files 2>&1 | tail -10
uv run pytest -q tests/test_miniapp_pages.py 2>&1 | tail -10
```
Pre-commit green. ConnectionRefusedError accepted (infra).

- [ ] **Step 7: Commit (do NOT push)**

```bash
git add app/templates/miniapp/_partials/task_sheet.html tests/test_miniapp_pages.py
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(γ): Mini App task_sheet — секция комментариев

Comments accordion после подзадач: lazy-fetch при раскрытии,
список с датой + удалением, textarea + кнопка отправки. Alpine-методы
loadComments/addComment/deleteComment бьют в /api/tasks/{id}/comments
(cookie-auth, тот же backend что и web). comments сбрасывается при
смене задачи в loadTask.
EOF
)"
```

## Context

- Working dir: `c:\www-Yaroslav\SchoolProject`. Branch `master`.
- Backend comments endpoints work with cookie-auth — Mini App's `attemptAuth()` already sets the cookie, so `/api/tasks/{id}/comments` is reachable from the sheet.
- Subtasks accordion in the same file is the closest reference pattern — replicate its style.

---

## Task 2: Context-menu — labels + comments actions, remove task_row hover-strip

**Files:**
- Modify: `app/templates/_partials/task_context_menu.html`
- Modify: `app/templates/_partials/task_row.html`

Closes the β3 concern: labels-popover + comments-toggle were stuck in a desktop hover-strip because the context menu lacked them. Add them to the context menu, then delete the hover-strip — `⋯` becomes the single action entry point.

- [ ] **Step 1: Read both files**

```bash
cat app/templates/_partials/task_context_menu.html
sed -n '160,215p' app/templates/_partials/task_row.html
```
In `task_context_menu.html` note:
- The `data-ctx="..."` button markup pattern (lines ~6-27).
- The JS `click` handler (`menu.addEventListener('click', ...)` ~line 154) — how it reads `btn.dataset.ctx` and dispatches. Note how `detail`/`edit` use `htmx.ajax(...)`.
- How the menu knows the current task id (there's a `currentTaskId` variable or it reads from the `[id^="task-wrap-"]` element).

In `task_row.html` note:
- The hover-strip block (`hidden lg:flex ... lg:group-hover:opacity-100`, ~lines 169-211 per β3) — its 3 buttons: labels-popover, comments-toggle, delete.
- The exact `hx-get` / `htmx.ajax` wiring for labels-popover (`/htmx/tasks/{id}/labels-popover`) and comments (`/htmx/tasks/{id}/comments`).

- [ ] **Step 2: Add two actions to `task_context_menu.html`**

Add two `data-ctx` buttons — place them near `edit`/`duplicate` (logical grouping), using the EXACT same `<button data-ctx="..." class="...">` markup as the existing items:

```html
<button data-ctx="labels" class="...same classes as siblings...">🏷 Лейблы</button>
<button data-ctx="comments" class="...same classes as siblings...">💬 Комментарии</button>
```

Match the existing icon approach — if siblings use inline SVG, use SVG; if they use emoji, use emoji. Read a sibling button first.

- [ ] **Step 3: Wire the two actions in the JS handler**

In the `menu.addEventListener('click', ...)` handler, add two branches. They should replicate what the old hover-strip buttons did. The hover-strip used:
- labels: `htmx.ajax('GET', '/htmx/tasks/' + id + '/labels-popover', {target: ..., swap: ...})` — copy the exact target/swap from `task_row.html`'s old button.
- comments: toggled `/htmx/tasks/{id}/comments` into the `#comments-slot-{id}` element — copy exact wiring.

```javascript
} else if (ctx === 'labels') {
  htmx.ajax('GET', '/htmx/tasks/' + currentTaskId + '/labels-popover', { /* target+swap copied from old button */ });
} else if (ctx === 'comments') {
  htmx.ajax('GET', '/htmx/tasks/' + currentTaskId + '/comments', { target: '#comments-slot-' + currentTaskId, swap: 'innerHTML' });
}
```

**Verify the exact target/swap** by reading the old hover-strip buttons in `task_row.html` — copy their `hx-target` / `hx-swap` values precisely. Use whatever variable the handler already uses for the task id (`currentTaskId` or equivalent).

- [ ] **Step 4: Remove the hover-strip from `task_row.html`**

Delete the `hidden lg:flex ... lg:group-hover:opacity-100` action-strip block (the 3-button strip). Keep:
- The `⋯` overflow button (it dispatches `contextmenu` — now covers labels+comments+everything).
- The `#comments-slot-{id}` and `#subtasks-of-{id}-slot` hidden slots — context-menu's comments action targets `#comments-slot-{id}`, so it MUST stay.
- All other wiring.

Verify slots survive:
```bash
grep -nE "id=\"(task-wrap|subtasks-of|comments-slot)" app/templates/_partials/task_row.html
```
All 3 must still be present.

- [ ] **Step 5: jinja-linter + pre-commit**

```bash
uv run python scripts/lint_templates.py app/templates/_partials/task_context_menu.html app/templates/_partials/task_row.html 2>&1 | tail -5
uv run pre-commit run --all-files 2>&1 | tail -10
```
0 errors / green.

- [ ] **Step 6: pytest**

```bash
uv run pytest -q 2>&1 | tail -15
```
If a test asserts the hover-strip buttons exist in task_row HTML (`grep -rln "labels-popover\|hover" tests/`) — update it: those actions moved to the context menu. ConnectionRefusedError accepted.

- [ ] **Step 7: Commit (do NOT push)**

```bash
git add app/templates/_partials/task_context_menu.html app/templates/_partials/task_row.html tests/
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "$(cat <<'EOF'
feat(γ): context-menu получил labels + comments — hover-strip убран

Закрыт β3-concern: labels-popover и comments-toggle добавлены в
task_context_menu как data-ctx="labels" / data-ctx="comments" с тем же
htmx.ajax-wiring что было в hover-strip. Desktop hover-strip из 3
кнопок удалён из task_row — теперь единственная точка входа в действия
это ⋯ (context-menu). Слоты comments-slot / subtasks-of сохранены.
EOF
)"
```

## Context

- Working dir: `c:\www-Yaroslav\SchoolProject`. Branch `master`.
- This closes the documented β3 concern (PROGRESS.md 2026-05-14 entry).
- `task_context_menu.html` uses vanilla JS, no Alpine/HTMX-declarative — the handler is a plain `addEventListener`.

---

## Task 3: Push + deploy + smoke + PROGRESS

- [ ] **Step 1: Sanity**

```bash
git log --oneline -5
```
Expected: γ1 + γ2 commits on top of `59fac30`.

- [ ] **Step 2: Push**

```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master 2>&1 | tail -3
```

- [ ] **Step 3: Wait deploy + verify prod HEAD matches local**

```bash
until curl -fsS https://getdoday.ru/health 2>/dev/null | grep -q "ok"; do sleep 5; done
```
Then SSH-poll prod `git rev-parse HEAD` until it matches local HEAD (max 5 min). Use paramiko, SSH_PASS from `.env`, host `getdoday.ru` user `getdoday`.

- [ ] **Step 4: Smoke 23/23**

```bash
uv run python scripts/smoke_test.py https://getdoday.ru 2>&1 | tail -8
```
Expected: `all 23 green`.

- [ ] **Step 5: Update PROGRESS.md**

Prepend (match existing entry style):
```markdown
## 2026-05-14 — Phase γ: comments UI завершён

Mini App task_sheet получил секцию комментариев (lazy-fetch accordion,
add/delete, бьёт в /api/tasks/{id}/comments). Web comments уже работали
с прошлых фаз — не трогали. Закрыт β3-concern: context-menu получил
labels + comments actions, desktop hover-strip из task_row убран —
единственная точка входа в действия теперь ⋯.

Smoke 23/23 GREEN. Next: Phase δ — team collaboration.
```

Commit + push:
```bash
git add PROGRESS.md
git -c user.email="112168281+SwairIt@users.noreply.github.com" -c user.name="SwairIt" commit -m "docs(γ): PROGRESS обновлён — comments UI завершён"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master 2>&1 | tail -3
```

- [ ] **Step 6: Report** — push output, prod HEAD match, smoke result, concerns.

---

## Self-Review (выполнено)

**Spec coverage:** γ spec = «comments UI polish». Web comments — recon подтвердил что УЖЕ работают (`task_detail.html:386`), не требуют работы. Mini App comments — Task 1. β3-concern (context-menu labels/comments) — Task 2. Task 3 — deploy.

**Placeholder scan:** нет TBD. Task 1/2 содержат «match existing pattern» guidance т.к. точная разметка accordion/context-menu зависит от house style — implementer читает файл первым шагом.

**Type/name consistency:** `loadComments`/`addComment`/`deleteComment` — консистентны между markup (`@click`) и Alpine-методами. `comments-slot-{id}` — консистентен между task_row (slot) и context-menu (htmx target).

**Scope check:** 3 tasks, последовательны. Task 2 — средний риск (трогает context-menu JS + task_row), implementer проинструктирован сохранять слоты.

---

## Execution Handoff

Continue with **subagent-driven-development**.
