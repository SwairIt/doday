# Public-Pages Responsive Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every public-facing page render correctly on mobile (375px), tablet landscape (1024px), and desktop (1440px) without breaking existing visual style — only adding Tailwind responsive prefixes.

**Architecture:** Per-page Playwright snapshot-fix-snapshot loop. Navigate live URL → take screenshots at 3 viewports → identify visual breaks → apply Tailwind responsive variants in template → re-screenshot to verify → commit. One commit per page.

**Tech Stack:** Tailwind CSS (CDN with inline config), Jinja2 templates, Playwright MCP for headless Chromium snapshots, our `scripts/lint_templates.py` for regression checks.

**Spec:** `docs/superpowers/specs/2026-05-08-public-pages-responsive-design.md`

---

## File Structure

8 templates in scope, in processing order:

```
app/templates/
├── landing.html            ← MOST COMPLEX, 321 classes, 29 already responsive
├── pricing.html            ← table + 3-col cards, 108 classes
├── auth/register.html      ← form + side panel, 74 classes, 5 already responsive
├── auth/login.html         ← single form, 46 classes, 5 already responsive
├── auth/verify_pending.html ← static info card, 23 classes, 0 responsive
├── help/index.html         ← article grid, 37 classes, 4 already responsive
├── help/article.html       ← long-form prose, 43 classes, 5 already responsive
└── privacy.html            ← legal text, 22 classes, 0 responsive
```

`base.html` is shared `<head>` only — no layout to adapt.

**Untouched:** `app/templates/app/*` (private app pages — separate spec later), `app/templates/_partials/*` (used only inside private app), `app/main.py`, all Python code.

---

## Common fix patterns (reference for all tasks)

| Symptom | Fix pattern |
|---|---|
| Hero `text-5xl/6xl/7xl` overflows on 375px | `text-3xl sm:text-4xl md:text-6xl lg:text-7xl` |
| `text-3xl md:text-4xl` heading overflow | `text-2xl sm:text-3xl md:text-4xl` |
| 3-column grid squashed on mobile | `grid-cols-1 md:grid-cols-3` (default mobile-first) |
| 4-column grid squashed | `grid-cols-2 md:grid-cols-4` (cards), or `grid-cols-1 sm:grid-cols-2 md:grid-cols-4` |
| Two-column form/aside grid breaks | `min-h-screen flex flex-col md:grid md:grid-cols-2` |
| Container too wide on mobile | `px-4 md:px-6 lg:px-8` |
| Table layout dies on mobile | wrap in `<div class="overflow-x-auto">` (already done in landing) |
| Long URL/email text overflows | `break-all` or `break-words` on the container |
| Image/SVG overflows | `max-w-full h-auto` |
| Button row overflows | add `flex-wrap` |
| Sticky nav overflows | `flex-wrap gap-3` on nav children |
| Modal/card too narrow with side margins | `max-w-[calc(100vw-2rem)] md:max-w-md` |
| Section padding too big on mobile | `py-12 md:py-20 lg:py-28` (instead of fixed `pb-28`) |
| Card-internal padding too big | `p-4 sm:p-5 md:p-7` |
| Stat number `text-4xl md:text-5xl` too big on tiny mobile | `text-3xl sm:text-4xl md:text-5xl` |

**Standard viewports for snapshot:**
- Mobile: 375 × 812 (iPhone SE / iPhone 12 mini)
- Tablet: 1024 × 768 (iPad landscape)
- Desktop: 1440 × 900 (laptop)

**Standard Playwright workflow per page (used by every task):**
1. `mcp__plugin_playwright_playwright__browser_resize` to viewport
2. `mcp__plugin_playwright_playwright__browser_navigate` to URL
3. `mcp__plugin_playwright_playwright__browser_take_screenshot` (full page)
4. Visually inspect the screenshot
5. Apply fixes to template via Edit
6. Repeat for the next viewport, comparing fixed page

**After all viewports verified:**
- `uv run python scripts/lint_templates.py app/templates` → must show 0 errors (warnings OK)
- `git add app/templates/<file>.html`
- `git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: <page> — адаптив для mobile/desktop"`

---

## Task 1: Landing — `/`

**Files:**
- Modify: `app/templates/landing.html`

**Pre-known likely issues (from static scan):**
- Hero `text-5xl md:text-6xl lg:text-7xl` may be too large on 375px — `text-5xl` = 48px = OK actually, but check
- Section padding `pb-28` (112px) might be excessive on mobile — consider `pb-16 md:pb-28`
- 4-stat grid `grid-cols-2 md:grid-cols-4` already responsive — verify
- 3-column feature cards `md:grid-cols-2 lg:grid-cols-3` already responsive — verify
- Pricing 3-col `md:grid-cols-3` — defaults to single col on mobile, verify card width OK
- Comparison table is `<div class="card overflow-x-auto"><table class="w-full text-sm min-w-[640px]">` — table scrolls horizontally on mobile, page itself doesn't scroll. Verify.
- 3-steps cards `md:grid-cols-3` — defaults to single col, verify
- Header nav: `<div class="hidden md:flex items-center gap-7 text-sm">` already hides on mobile, login/register buttons stay
- Footer 4-col `md:grid-cols-4` — defaults to single col on mobile, verify

- [ ] **Step 1: Snapshot mobile (375 × 812)**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=landing-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=landing-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=landing-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect screenshots, identify breaks**

For each viewport, write down:
- Any horizontal scroll on the page (body width > viewport)
- Text that overflows containers or is illegibly small
- Cards/grids stacked badly
- Touch targets < 36px on mobile
- Pre-known issues from above — verify each

If a viewport shows zero issues — note "viewport <X> clean, no fix needed".

- [ ] **Step 5: Apply fixes**

For each issue, apply the corresponding pattern from the "Common fix patterns" reference table at the top of this plan. Use the Edit tool on `app/templates/landing.html`. Make all fixes in this single editing pass before re-screenshotting.

Don't touch CSS variables, colors, gradients, or animations. Only Tailwind class additions.

- [ ] **Step 6: Re-snapshot all 3 viewports after fixes**

Re-run Steps 1-3 with `-after` suffix on filenames. Visually compare before/after. If issues remain — repeat Step 5. Maximum 3 fix iterations.

- [ ] **Step 7: Run jinja-linter (regression check)**

Run: `uv run python scripts/lint_templates.py app/templates`
Expected: `0 error(s), 100 warning(s)` (or similar warning count — error count must be 0).

If errors appear: investigate. Most likely a `|tojson|safe` accidentally introduced — revert the offending change.

- [ ] **Step 8: Commit**

```bash
git add app/templates/landing.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: landing — адаптив для mobile/desktop"
```

Don't push individually — pushes happen at end of plan to batch CI runs.

---

## Task 2: Pricing — `/pricing`

**Files:**
- Modify: `app/templates/pricing.html`

**Pre-known likely issues:**
- Header `class="sticky top-0 z-20 glass border-b border-[var(--border)] px-6 py-3 flex items-center gap-4"` — gap-4 with brand + monthly/annual toggle + back-button might overflow on 375px → add `flex-wrap` or hide elements with `hidden sm:flex`
- 3-column tariff grid `md:grid-cols-3` — defaults to 1 col on mobile, verify card width
- Card-internal text-[10px] badges — already small (warning-level)
- FAQ `max-w-3xl` — fits, but check side padding
- Headline text might need mobile size cap

- [ ] **Step 1: Snapshot mobile (375 × 812) of `https://getdoday.ru/pricing`**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/pricing
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=pricing-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/pricing
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=pricing-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/pricing
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=pricing-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Same checklist as Task 1 Step 4. Pay attention to:
- Sticky header overflow on mobile
- Tariff cards width on 375px
- Annual/monthly toggle on mobile
- FAQ text readability

- [ ] **Step 5: Apply fixes per common patterns**

Edit `app/templates/pricing.html`. Common fixes for this page:
- Header overflow: add `flex-wrap gap-3` or hide back-button with `hidden sm:inline-flex`
- Tariff cards: ensure `gap-6` is `gap-4 md:gap-6` if cards too tight
- Card padding: `p-7` → `p-5 md:p-7` if too cramped on mobile

- [ ] **Step 6: Re-snapshot 3 viewports**

Repeat Steps 1-3 with `-after`. Compare.

- [ ] **Step 7: Run linter**

`uv run python scripts/lint_templates.py app/templates` — must be 0 errors.

- [ ] **Step 8: Commit**

```bash
git add app/templates/pricing.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: pricing — адаптив для mobile/desktop"
```

---

## Task 3: Register — `/auth/register`

**Files:**
- Modify: `app/templates/auth/register.html`

**Pre-known likely issues:**
- Layout: `<div class="min-h-screen grid md:grid-cols-2">` — already grid on md+, single column on mobile (form on top, marketing aside below). Verify the marketing aside isn't unhealthy on mobile (currently `hidden md:flex` — good, hidden entirely).
- Audience picker `grid grid-cols-3 gap-2` — 3 cards × ~110px each = 330px on mobile (fits 375px), verify
- Floating-label form on mobile — verify labels don't clip
- Password strength meter alignment on narrow screen
- Privacy checkbox alignment

- [ ] **Step 1: Snapshot mobile (375 × 812) of `https://getdoday.ru/auth/register`**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/register
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=register-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/register
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=register-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/register
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=register-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Pay attention to:
- Audience picker (3 cards) — width per card on 375px should be ≥100px
- Form input padding on mobile
- "14 дней Pro в подарок" tagline text size
- Marketing aside on tablet (1024px is md+ — should show)

- [ ] **Step 5: Apply fixes**

Common fixes for register:
- Padding container: `px-6 md:px-12 py-8` → already responsive
- Audience cards if too cramped: `text-[10px]` already there, can stay
- Form input padding `px-4 py-3` is fine

If marketing aside cuts off content on tablet (1024px), consider `lg:flex` instead of `md:flex`.

- [ ] **Step 6: Re-snapshot 3 viewports**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit**

```bash
git add app/templates/auth/register.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: auth/register — адаптив для mobile/desktop"
```

---

## Task 4: Login — `/auth/login`

**Files:**
- Modify: `app/templates/auth/login.html`

**Pre-known likely issues:**
- Same layout as register (split + marketing aside)
- Simpler form (just email + password)
- Less likely to break — but check anyway

- [ ] **Step 1: Snapshot mobile (375 × 812) of `https://getdoday.ru/auth/login`**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/login
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=login-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/login
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=login-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/login
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=login-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Same checklist. This page is simple — most likely no fixes needed beyond what register taught us.

- [ ] **Step 5: Apply fixes (if any)**

If no breaks at any viewport — note "no changes needed for login.html" and skip to Step 7.

- [ ] **Step 6: Re-snapshot if changes made**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit (if changes made)**

```bash
git add app/templates/auth/login.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: auth/login — адаптив для mobile/desktop"
```

If no changes were needed — skip the commit and proceed to Task 5.

---

## Task 5: Verify Pending — `/auth/verify-pending`

**Files:**
- Modify: `app/templates/auth/verify_pending.html`

**Pre-known likely issues:**
- 0 responsive prefixes currently
- Single centered card with success icon — likely fits all viewports
- Card padding `p-10` might be too tight or too padded on mobile

- [ ] **Step 1: Snapshot mobile (375 × 812)**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/verify-pending
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=verify-pending-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/verify-pending
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=verify-pending-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/auth/verify-pending
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=verify-pending-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Check icon sizing (`w-16 h-16`), card padding, text size, "← Вернуться ко входу" link target size.

- [ ] **Step 5: Apply fixes (if any)**

Common: card padding `p-10` → `p-6 md:p-10` if too padded on mobile.

- [ ] **Step 6: Re-snapshot if changes made**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit (if changes made)**

```bash
git add app/templates/auth/verify_pending.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: auth/verify-pending — адаптив для mobile/desktop"
```

---

## Task 6: Help Index — `/help`

**Files:**
- Modify: `app/templates/help/index.html`

**Pre-known likely issues:**
- Article grid (likely `md:grid-cols-2` or `md:grid-cols-3`)
- Search input width on mobile
- Category navigation if present

- [ ] **Step 1: Snapshot mobile (375 × 812)**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/help
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-index-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/help
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-index-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/help
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-index-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Article cards are the main visual element — verify they stack cleanly and maintain readable card content on mobile.

- [ ] **Step 5: Apply fixes**

Common: article grid `md:grid-cols-3` → `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` for smoother degradation.

- [ ] **Step 6: Re-snapshot 3 viewports**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit**

```bash
git add app/templates/help/index.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: help/index — адаптив для mobile/desktop"
```

---

## Task 7: Help Article — `/help/<slug>`

**Files:**
- Modify: `app/templates/help/article.html`

**Pre-known likely issues:**
- Long-form prose — needs comfortable reading width on desktop, full-width on mobile
- Code blocks — must wrap or scroll horizontally
- Prev/next navigation at bottom (`<a>Назад</a>` / `<a>Далее</a>`)
- Sidebar table-of-contents if present

- [ ] **Step 1: Snapshot mobile (375 × 812) of `https://getdoday.ru/help/start`**

(Use any article slug — `/start` is the canonical one. If 404 — try `/inbox` or any other from `app/help/articles.py`.)

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/help/start
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-article-mobile-before.png, fullPage=true
```

If 404, fall back to:
```
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/help/inbox
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-article-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=help-article-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Specific concerns:
- Code blocks (`<pre>`) — must have `overflow-x-auto` so they scroll instead of breaking page width
- Prev/next nav cards — must stack on mobile if currently side-by-side
- Reading line length on desktop — `max-w-3xl` is comfortable, verify

- [ ] **Step 5: Apply fixes**

Common for article pages:
- `<pre>` overflow: ensure existing styles handle it (they do via base.html `.help-prose pre` rules — verify in screenshot)
- Prev/next nav: if grid `grid-cols-2`, change to `grid-cols-1 md:grid-cols-2 gap-3`

- [ ] **Step 6: Re-snapshot 3 viewports**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit**

```bash
git add app/templates/help/article.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: help/article — адаптив для mobile/desktop"
```

---

## Task 8: Privacy — `/privacy`

**Files:**
- Modify: `app/templates/privacy.html`

**Pre-known likely issues:**
- 0 responsive prefixes
- Pure long-form legal text — likely needs only padding adjustment
- Risk: text might run edge-to-edge on mobile if no `px-` is set

- [ ] **Step 1: Snapshot mobile (375 × 812)**

```
mcp__plugin_playwright_playwright__browser_resize: width=375, height=812
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/privacy
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=privacy-mobile-before.png, fullPage=true
```

- [ ] **Step 2: Snapshot tablet (1024 × 768)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1024, height=768
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/privacy
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=privacy-tablet-before.png, fullPage=true
```

- [ ] **Step 3: Snapshot desktop (1440 × 900)**

```
mcp__plugin_playwright_playwright__browser_resize: width=1440, height=900
mcp__plugin_playwright_playwright__browser_navigate: url=https://getdoday.ru/privacy
mcp__plugin_playwright_playwright__browser_take_screenshot: filename=privacy-desktop-before.png, fullPage=true
```

- [ ] **Step 4: Inspect, identify breaks**

Plain legal page — main concerns: padding edges, font size, headings hierarchy visibility.

- [ ] **Step 5: Apply fixes**

Likely fixes:
- Container: add `max-w-3xl mx-auto px-4 md:px-6 py-8 md:py-12` if missing
- Headings: ensure `<h1>` not too giant on mobile

- [ ] **Step 6: Re-snapshot 3 viewports**

- [ ] **Step 7: Run linter**

- [ ] **Step 8: Commit**

```bash
git add app/templates/privacy.html
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "style: privacy — адаптив для mobile/desktop"
```

---

## Task 9: Final verification + push + PROGRESS update

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run jinja-linter on all templates**

Run: `uv run python scripts/lint_templates.py app/templates`
Expected: `0 error(s), N warning(s)` (warnings unchanged from baseline ~100)

- [ ] **Step 2: Run full pytest**

Run: `uv run pytest -q`
Expected: 626 passed (or however many — must match the green baseline). No new failures introduced by template changes.

If no Postgres locally — skip. CI will catch any test regressions.

- [ ] **Step 3: Push all 8 commits**

```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
```

Expected: 8 commits pushed (or fewer if some pages had no fix needed).

- [ ] **Step 4: Wait for CI to complete**

Use Monitor or manual API poll to confirm CI run on the latest commit shows `conclusion=success`.

If CI red — investigate, fix, re-push.

- [ ] **Step 5: Run live smoke-test against prod**

Wait for redeploy script to run (or trigger manually via `python .tmp_ssh_inspect.py`).

Run: `uv run python scripts/smoke_test.py https://getdoday.ru`
Expected: 18/18 green.

- [ ] **Step 6: Update PROGRESS.md**

Append to `PROGRESS.md` under the Lifetime log section, after the most recent entry:

```markdown
### 2026-05-09 — public-pages responsive адаптив

По плану `docs/superpowers/plans/2026-05-09-public-pages-responsive.md`. 8 публичных шаблонов (landing, pricing, 3 auth, help index/article, privacy) проверены на 3 viewport'ах (375/1024/1440) через Playwright. Применены Tailwind responsive-prefixes на найденных breaks. Стиль и контент не тронуты.

Финальная проверка: jinja-линтер 0 errors, pytest 626 passed, smoke-test 18/18 green, CI на master зелёный.

Out-of-scope: app-страницы `/app/*` — отдельный спринт.
```

- [ ] **Step 7: Commit + push PROGRESS update**

```bash
git add PROGRESS.md
git -c user.email='112168281+SwairIt@users.noreply.github.com' commit -m "docs: PROGRESS — public-pages responsive адаптив завершён"
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
```

---

## Self-Review

**1. Spec coverage:**
- Pages in scope (8 templates) → Tasks 1-8 ✓
- Workflow per page (snapshot → fix → re-snapshot → commit) → matches spec ✓
- Common fix patterns (provided in spec) → mirrored in plan reference table ✓
- Three viewports (375, 1024, 1440) → consistent across all tasks ✓
- Acceptance criteria (no horizontal scroll, ≥36px touch targets, etc.) → covered by Step 4 inspect ✓
- One commit per page → matches Step 8 of each task ✓
- Final smoke-test, linter, CI verification → Task 9 ✓

**2. Placeholder scan:**
- Steps 5 ("apply fixes") describe a class of fixes from a reference table, not specific code — this IS visual judgment work, exact fixes can't be predicted. Mitigation: every task has pre-known likely issues based on static scan, so the agent has a starting checklist. Marked as acceptable for visual UI work.
- No "TBD", no "implement later", no "similar to Task N".

**3. Type consistency:**
- File paths consistent (`app/templates/<file>.html` everywhere)
- Playwright tool calls have consistent parameter style
- Commit messages follow same `style: <page> — адаптив для mobile/desktop` template
- Git author email override consistent

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-09-public-pages-responsive.md`. Two execution options:

**1. Subagent-Driven** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
**Caveat:** subagents do NOT have Playwright MCP tools (only general-purpose ones do not get visual tools). For this plan, the controller (me) must take screenshots and provide the issue list to the subagent, then the subagent applies fixes via Edit. Inverts the normal pattern.

**2. Inline Execution (recommended for this plan)** — I execute tasks in this session using executing-plans. I have Playwright tools, can take screenshots, identify issues, apply fixes, and commit — all in one flow without dispatching. Faster iteration for visual work.

Which approach?
