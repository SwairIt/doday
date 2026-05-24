# design.md — правила дизайна и стиля Doday

Источник истины — `app/templates/base.html` (lines 65-479 у меня в чтении) + `app/templates/miniapp/_base.html` (Mini App альт-палитра) + `app/templates/landing.html` (паттерны секций). Этот файл — извлечённая спецификация, по которой нужно проверять любую новую вёрстку.

Дата: 2026-05-18
Применимо к: getdoday.ru (web + miniapp), не applicable к Telegram-боту (текст).

---

## 1. Цветовая палитра

### 1.1 Brand (фиолетовая шкала)

| Token | Hex | Применение |
|---|---|---|
| brand-50 | `#faf5ff` | very light backgrounds |
| brand-100 | `#f3e8ff` | light fills |
| brand-200 | `#e9d5ff` | secondary borders light theme |
| brand-300 | `#d8b4fe` | dark theme highlights |
| brand-400 | `#c084fc` | hover states dark theme |
| brand-500 | `#a855f7` | links / accents |
| brand-600 | `#9333ea` | primary action gradient end |
| brand-700 | `#7c3aed` | **core brand** — accent default, gradient start |
| brand-800 | `#6b21a8` | dark theme accent variant |
| brand-900 | `#4c1d95` | deep contrast |
| brand-950 | `#2e1065` | almost-black accent |

**`#7c3aed` — главный hex.** Используется в `theme-color` meta-теге, в логотипе, в gradient'е, в Mini App TG button color.

### 1.2 Ink (text/surface шкала)

| Token | Hex | Применение |
|---|---|---|
| ink-50 | `#f5f3ff` | text on dark bg |
| ink-100 | `#ede9fe` | high-contrast text dark |
| ink-200..400 | оттенки | muted text |
| ink-500 | `#6b6587` | text-muted light theme |
| ink-700 | `#4a4170` | strong text light theme |
| ink-900 | `#1a1230` | body text light theme |
| ink-950 | `#0d0820` | bg dark theme |

### 1.3 Accent gradient

`--grad-from: #7c3aed` → `--grad-to: #d946ef` — линейный 135°.

Применяется через:
- `.grad-bg` class
- `.grad-text` (bg-clip: text)
- `.btn-primary` background

### 1.4 Семантические

| Token | Hex | Назначение |
|---|---|---|
| `--success` | `#10b981` | success / done |
| `--warning` | `#f59e0b` | warning |
| `--danger` | `#ef4444` | error / delete |

### 1.5 CSS-переменные (живой контракт)

```css
:root {
  --bg, --surface, --surface-2, --border,
  --text, --text-muted, --accent, --accent-2,
  --grad-from, --grad-to,
  --success, --warning, --danger,
  --shadow-sm, --shadow, --shadow-lg, --shadow-glow
}
```

**Никогда** не хардкодь цвета внутри новых компонентов — всегда через `var(--name)` или Tailwind brand-* классы. Это даёт автомат-переключение light/dark + accent variants.

### 1.6 Accent variants (по `data-accent` на `<html>`)

- `default` — фиолетовый (нет атрибута)
- `sunset` — `#f97316 → #ec4899` оранж-розовый
- `forest` — `#10b981 → #06b6d4` зелёно-бирюзовый
- `minimal` — `#525252 → #18181b` серо-чёрный

Юзер переключает на /app/settings, сохраняется в `localStorage.doday-accent`.

---

## 2. Темы

### 2.1 Light / Dark / System

Хранится в `localStorage.doday-theme`. Резолвится inline-скриптом в `<head>` до первого paint (anti-flash). Атрибут `data-theme="light|dark"` на `<html>`.

System режим следит за `prefers-color-scheme` через matchMedia + переключается динамически.

### 2.2 Default

- **Web app**: `system` (по дефолту), fallback `dark` при exception
- **Mini App**: `light` (TG чаще светлый), резолвится через `tg.colorScheme` в miniapp.js

### 2.3 Dark palette

```
--bg: #0d0820       (ink-950)
--surface: #161028
--surface-2: #1f1638
--border: #2a2048
--text: #f5f3ff     (ink-50)
--text-muted: #9890b8 (ink-400)
--accent: #a78bfa
```

### 2.4 Light palette

```
--bg: #fafaff
--surface: #ffffff
--surface-2: #f5f3ff
--border: #e9e5f6
--text: #1a1230     (ink-900)
--text-muted: #6b6587 (ink-500)
--accent: #7c3aed   (brand-700)
```

### 2.5 Mini App палитра

Отдельная (более «Telegram-ish»): `#0f0f1a` bg dark, `#1c1c2e` secondary; light — `#ffffff` / `#f1f5f9` slate. Брэнд-цвет тот же `#7c3aed`.

---

## 3. Типографика

### 3.1 Шрифт

`Inter` через Google Fonts, веса **400, 500, 600, 700, 800**.

Fallback: `ui-sans-serif, system-ui, sans-serif`.

В Mini App — нативный system-sans (Apple/Segoe UI/Roboto) для consistency с TG chrome.

### 3.2 Features

- `font-feature-settings: 'cv11', 'ss01'` — стилевые альтернаты Inter (округлая «а»)
- `-webkit-font-smoothing: antialiased`

### 3.3 Heading scale (Tailwind)

| Heading | Класс | Размер |
|---|---|---|
| H1 hero | `text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]` | 36/48/60/72 px |
| H2 section | `text-3xl md:text-4xl font-bold` | 30/36 px |
| H3 card | `text-lg sm:text-2xl font-bold` | 18/24 px |

### 3.4 Body

- `text-base sm:text-lg md:text-xl` для лидов
- `text-sm` для muted captions / labels
- `text-xs` для микро-labels (uppercase tracking-widest для секционных eyebrow)

### 3.5 Text wrapping

- `text-wrap: balance` для headings (h1-h4) — красивый перенос
- `text-wrap: pretty` для p, li, blockquote — без single-word-orphan

---

## 4. Spacing

### 4.1 Контейнеры

- `max-w-2xl` (672px) — узкие layouts (auth, settings)
- `max-w-5xl` (1024px) — лендинг hero, mock screenshot
- `max-w-7xl` (1280px) — широкие grid'ы (features, footer nav)

### 4.2 Padding pattern (responsive)

`px-4 sm:px-6` — стандарт horizontal padding контейнера.

Section vertical padding:
- Hero: `pt-12 sm:pt-20 pb-16 sm:pb-24`
- Section: `pb-20 sm:pb-28`

### 4.3 Gap

- Между элементами в группе: `gap-2 / gap-3`
- Между cards в grid: `gap-6`
- Между sections: `pb-20 sm:pb-28`

### 4.4 Mobile safe-area

В Mini App: `padding-bottom: calc(64px + env(safe-area-inset-bottom))` для bottom-nav clearance. Везде где есть fixed bottom — учитывать `env(safe-area-inset-bottom)`.

---

## 5. Компоненты

### 5.1 Button — `.btn-primary`

Градиент-фон (brand → fuchsia), белый текст, font-weight 600, padding 11x20, border-radius 12, `shadow-lg` (фиолетовая glow).

Hover: `translateY(-1px)`, +glow shadow, brightness 1.06.
Active: `scale(0.97)`.
Disabled: opacity 0.55, grayscale 0.3, no transform.

**Когда:** primary action на странице. Один на view.

### 5.2 Button — `.btn-ghost`

Surface-фон, border, font-weight 500, такой же padding.

Hover: surface-2 fill, border-color → accent-mix.

**Когда:** secondary action рядом с primary; navigation buttons.

### 5.3 Input — `.input`

Surface bg, border, radius 10, padding 12x14, full-width.

Focus: border → accent, 4px focus ring (accent-mix 18% alpha).

### 5.4 Card — `.card` + `.card-hover`

Surface bg, border, radius **16**, shadow-sm.

`.card-hover` добавляет: hover → translateY(-2px), shadow-card, border → accent-mix 25%.

**Когда:** любая standalone-секция контента (task, project, feature on landing).

### 5.5 Glass — `.glass`

`color-mix(in oklab, surface 72%, transparent)`, backdrop-blur 14px, saturate 180%.

**Когда:** sticky header, modal overlays, любая semi-transparent panel.

### 5.6 Grad — `.grad-text` / `.grad-bg`

`.grad-text`: bg линейный 135° + bg-clip:text + color:transparent
`.grad-bg`: тот же gradient как background

**Когда:** brand-моменты, hero h1 акценты, important badges.

### 5.7 Bottom-nav (только Mini App) — `.miniapp-nav`

Fixed bottom, `grid-template-columns: repeat(5, 1fr)`, surface-2 bg, top-border, safe-area-aware padding.

Items: column flex, icon 22x22 stroke-2, label 10px. Active = accent color + bold.

---

## 6. Радиусы

| Use | Radius | CSS |
|---|---|---|
| Tags / pills / chips | `rounded-full` | 9999px |
| Sm controls (cells, badges) | `rounded-md` | 6px |
| Buttons / inputs | `rounded-xl` / `12px` | 12px |
| Modals / cards | `rounded-2xl` / `16px` | 16px |
| Page hero blocks | `rounded-3xl` | 24px |

---

## 7. Тени

| Token | Light theme | Dark theme |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(31,16,56,0.04)` | `0 1px 2px rgba(0,0,0,0.4)` |
| `--shadow` | `0 4px 12px -2px rgba(31,16,56,0.08)` | `0 6px 20px -4px rgba(0,0,0,0.5)` |
| `--shadow-lg` | `0 16px 40px -8px rgba(124,58,237,0.18)` | `0 24px 60px -12px rgba(124,58,237,0.35)` |
| `--shadow-glow` | `0 0 60px -20px rgba(124,58,237,0.45)` | `0 0 80px -20px rgba(167,139,250,0.55)` |
| `--shadow-card` | `0 16px 40px -8px rgba(124,58,237,0.18)` | (тот же) |

Glow = brand-color blur используется только для primary actions / brand moments. Не для каждой карточки.

---

## 8. Анимации

### 8.1 Keyframes

- `fade-in` — 200ms ease-out (opacity)
- `slide-up` — 240ms cubic-bezier (translateY 8px + opacity)
- `pop-in` — 280ms cubic-bezier (scale 0.96 + opacity)
- `float-slow` — 6s ease-in-out infinite (translateY ±10px) для ambient orbs
- `shimmer-bg` — 8s ease infinite (background-position 0→100%) для shimmer h1
- `confetti-fall` — 2.4s — для celebration
- `.reveal` IntersectionObserver triggered — 700ms reveal on scroll

### 8.2 Transition timing

Стандарт: `150ms` для hover-states (background, border-color, color).
Transform: `90ms` для active.
Pop-in: `200-280ms` для появления.

### 8.3 prefers-reduced-motion

Глобальный override:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Соблюдай.** Любая новая анимация должна работать при `reduce`.

---

## 9. Ambient background

`body::before` — фиксированный gradient orbs, pointer-events: none, z-index: 0:

```css
radial-gradient(900px 700px at 100% -10%, rgba(168,85,247,0.18), transparent 60%)
radial-gradient(1000px 800px at -10% 110%, rgba(217,70,239,0.14), transparent 60%)
```

Light theme — то же с 0.10/0.08 opacity. Accent variants override.

main/header/nav/footer — `position: relative; z-index: 1` чтобы быть над orbs.

---

## 10. Iconography

- Heroicons-style stroke icons, `stroke-width: 2` (2.5 на крупных), `stroke-linecap: round`
- Размеры: 16x16 (inline в тексте), 20x20, 24x24
- Inline SVG в шаблонах (нет sprite/font иконок)
- На primary buttons — иконка 16x16 справа от текста

---

## 11. Focus / A11y

- `:focus-visible` всегда — 2px outline accent, offset 2px, radius 6
- `<a href="#main-content">` skip-link — sr-only до focus → fixed top-left pill
- ARIA labels на icon-only buttons
- `aria-label`, `aria-current="page"` для navigation
- `data-theme` управляется JS — но также `color-scheme: dark light` для нативных browser controls

---

## 12. Markdown rendering — `.md-preview`

Класс на любом блоке где рендерится user-typed markdown (descriptions, comments):

- h1 1.25rem 700; h2 1.1rem 600; h3 1rem 600
- p 0.4em margin
- ul / li 1.4em padding-left, disc
- code: surface bg, 0.05/0.35em pad, radius 4, 0.9em font
- pre: surface bg + border, 8px radius, overflow-x:auto
- a: accent + underline
- strong 700; em italic

Реализация: `window.dodayMd(text)` в base.html (lines 117-141). HTML-escape → subset markdown.

---

## 13. Print stylesheet

`@media print`:

- Скрыть: `aside, header, nav, button, .focus-exit-pill, [class*="hx-"], #task-detail-slot, .confetti-stage, [x-show], [x-cloak], body::before`
- Body: white bg, black text
- `.card` — single 1px ccc border, без shadow, white bg
- Gradient text → solid black
- Links → `#0645ad` underline, URL после `:after`
- `h1-h3` page-break-after: avoid
- `li, .task-row` page-break-inside: avoid

**Соблюдай:** любая новая интерактивная вещь должна быть `display: none !important` в print.

---

## 14. Scrollbar custom

```css
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: color-mix(in oklab, var(--accent) 50%, var(--border)); }
```

---

## 15. Focus mode

`body.focus-mode` — скрывает aside/header/nav. Контент центрируется `max-width: 760px`. Toggle через `f` shortcut. Exit pill вверху справа.

---

## 16. Стили лендинга (specific)

### 16.1 Reveal на скролле

`.reveal` — opacity 0 + translateY 24px → IntersectionObserver добавляет `.in` → opacity 1 + translateY 0, transition 700ms. Threshold 0.12.

Delays: `.reveal-delay-100/200/300` (0.1/0.2/0.3s).

### 16.2 Hero blob orbs

`absolute` violet-500/20 + fuchsia-500/20 круги с blur-3xl + `float-slow` animation.

### 16.3 Stats grid

`grid-cols-2 md:grid-cols-4 gap-8 text-center`. Цифра — `text-4xl md:text-5xl grad-text font-bold`. Subtitle — `text-sm text-muted`.

### 16.4 Features grid

`grid md:grid-cols-2 lg:grid-cols-3 gap-6`. Каждая фича в `.card` + `.card-hover`. Иконка вверху + h3 + p.

### 16.5 Eyebrow

Section заголовки начинаются с маленького eyebrow:
```html
<p class="text-sm uppercase tracking-widest grad-text font-semibold mb-3">Возможности</p>
<h2 class="text-3xl md:text-4xl font-bold mb-3">Title</h2>
```

### 16.6 Sticky header

`sticky top-0 z-30 glass` + nav `max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between`.

Logo: violet square 8x8/9x9 `grad-bg rounded-xl text-white font-extrabold shadow-glow` + grad-text «Doday».

### 16.7 CTA pairs

Primary + ghost button рядом, `flex-col sm:flex-row gap-3 sm:gap-4`. Mobile — stack column, desktop — row.

---

## 17. Mobile-first правила

- Любая новая страница — сначала mobile (320px) → потом sm (640) → md (768) → lg (1024) → xl (1280)
- Sidebar: `hidden md:block`; mobile — `mobile_nav.html` снизу
- Hero h1 — 36px на mobile, 72px на 2xl
- Padding: `px-4 sm:px-6` (16 → 24)
- Кнопки full-width на mobile, fit-content на desktop
- Touch targets минимум **44x44** (Apple HIG)
- Никогда не horizontal scroll на mobile

---

## 18. Селекшн / интерактив

- `::selection` — accent 35% mix bg, regular text color
- Cursor: pointer на all clickable элементах
- Drag handle: `cursor: grab` → `grabbing` на active

---

## 19. Что НЕЛЬЗЯ

- ❌ Inline-styles в шаблонах (использовать Tailwind utilities + CSS vars)
- ❌ Хардкод hex-цветов без CSS var обёртки
- ❌ JS-only анимации (если можно CSS — то CSS, для prefers-reduced-motion override)
- ❌ Кастомные шрифты помимо Inter / system
- ❌ Radius меньше 4px на UI controls (выглядит «техничнее»-меньше юзеру)
- ❌ Тени без brand-tint (используй `--shadow-*` переменные, не raw rgba)
- ❌ Иконки не в stroke-style heroicons
- ❌ Animation > 300ms на UI transitions (только reveal/celebration могут быть длиннее)
- ❌ Disabled state без явного `opacity` + `cursor: not-allowed`
- ❌ Игнорировать `prefers-reduced-motion`
- ❌ Игнорировать `:focus-visible`
- ❌ Inline эмодзи как UI-иконки (только SVG)

---

## 20. Что ДОЛЖНО быть на каждой новой странице

- [ ] Extends `base.html` (web) или `miniapp/_base.html` (Mini App)
- [ ] `{% block title %}` с осмысленным заголовком (для tab + SEO)
- [ ] `{% block seo_description %}` если public-страница
- [ ] `<main>` с `position: relative` (над body::before orbs)
- [ ] Responsive padding (`px-4 sm:px-6`)
- [ ] Container max-width (`max-w-2xl` / `max-w-5xl` / `max-w-7xl`)
- [ ] Use components: `.btn-primary`, `.btn-ghost`, `.input`, `.card`, `.glass`, `.grad-text`
- [ ] CSS vars (--bg, --text, --accent), не raw hex
- [ ] Focus-visible на всех intractive
- [ ] Touch targets ≥ 44x44 на mobile
- [ ] Тестировать в light/dark/system + во всех 4 accents (default/sunset/forest/minimal)
- [ ] Print preview — выглядит читаемо
- [ ] Lighthouse: A11y ≥ 95, Performance ≥ 90 mobile

---

## 21. Версия

v1.0 — 2026-05-18. Извлечено из текущего `base.html` после Doday δ-phase.

Источники:
- `app/templates/base.html` (lines 65-479) — Tailwind config + CSS vars + components + animations + print
- `app/templates/miniapp/_base.html` (lines 40-130) — Mini App палитра + bottom-nav
- `app/templates/landing.html` (lines 12-200) — reveal patterns + hero + stats + features grid
- Статистика использования: 49 `btn-primary`, 54 `btn-ghost`, 90 `card` в шаблонах

---

## 22. Mobile gestures (Mini App + responsive web)

### 22.1 Swipe-actions на task row

В Mini App `_partials/task_card.html` поддерживает:
- **Swipe-left** (translateX -110%) → «Перенести на завтра» / snooze
- **Swipe-right** (translateX +110%) → «Готово» (complete)

CSS-state classes:
- `.swipe-row.swiping` — отключает transition пока юзер тянет
- `.swipe-row.completing` — animate `max-height: 0` после done
- `.swipe-row.removed` — translateX(-110%) + opacity 0
- `.swipe-row.snoozed` — translateX(110%) + opacity 0

JS — vanilla touch-events в `app/miniapp/static.py` (нет Hammer.js).

### 22.2 Drag-to-reorder (sortable.js)

`Sortable.create(element, { handle: '.drag-handle', animation: 150 })`.
Используется в:
- Sidebar projects (`_partials/sidebar.html`)
- Sections within project
- Tasks within section
- Kanban columns

### 22.3 HapticFeedback (Mini App only)

`Telegram.WebApp.HapticFeedback.impactOccurred('light')` — на complete / delete / move.
`'medium'` — на drag-end.
`'heavy'` — на error.

### 22.4 Pull-to-refresh

НЕ имплементирован осознанно (HTMX swap покрывает refresh-cases).

---

## 23. Bottom-sheet / modal patterns

### 23.1 Mini App task_sheet

`_partials/task_sheet.html` — bottom-sheet с задачей:
- `position: fixed; bottom: 0; left: 0; right: 0`
- `transform: translateY(100%)` → `translateY(0)` при open
- `transition: transform 280ms cubic-bezier(0.16, 1, 0.3, 1)` (spring-soft)
- `border-radius: 16px 16px 0 0`
- Handle bar сверху для swipe-to-close

### 23.2 Web modals

`_partials/new_project_modal.html`, `edit_project_modal.html`, `share_modal.html`, `upgrade_modal.html`. Структура:
- Overlay: `fixed inset-0 bg-black/40 z-40`
- Container: `fixed inset-0 z-50 flex items-center justify-center p-4`
- Content: `.card max-w-md w-full animate-pop-in`
- Close: иконка X в top-right + Esc key + overlay click
- Focus trap: первый input получает focus на open
- Body scroll lock: `overflow: hidden` на `<html>` пока open

### 23.3 Alpine pattern

```html
<div x-data="{ open: false }" x-show="open" x-transition.opacity>
  <div @click.away="open = false" @keydown.escape="open = false">
    ...
  </div>
</div>
```

---

## 24. Loading states / skeleton

### 24.1 HTMX indicator

```html
<button hx-post="/api/save" hx-indicator="#save-spinner">
  Save <span id="save-spinner" class="htmx-indicator">spinner</span>
</button>
```

`.htmx-indicator` скрыт по умолчанию, показывается во время request.

### 24.2 Skeleton loaders

Для медленных загрузок:
```html
<div class="animate-pulse">
  <div class="h-4 bg-[var(--surface-2)] rounded w-3/4"></div>
</div>
```

### 24.3 Spinner для button

Inline SVG с `animate-spin` Tailwind утилитой.

---

## 25. Empty states

### 25.1 Mini App templates

`_partials/empty_*.html`:
- `empty_today.html`
- `empty_inbox.html`
- `empty_calendar.html`
- `empty_projects.html`
- `empty_search.html`

Структура: emoji + headline + (опц.) CTA-кнопка.

### 25.2 Web empty states

Inline в `today.html`:
```html
<div class="card p-8 text-center">
  <div class="text-5xl mb-3">checkmark</div>
  <h3 class="font-semibold mb-1">Все задачи сделаны</h3>
  <p class="text-[var(--text-muted)]">Время на чашку чая.</p>
</div>
```

### 25.3 Правила

- Используй emoji или иконку (не пустой div)
- Краткий headline (до 5 слов)
- Опц. CTA-кнопка
- НЕ показывай error message в empty state

---

## 26. Error states

### 26.1 4xx pages

- `404.html` — «Страница не найдена», `.btn-ghost` назад на `/app/today`
- Auth 401 → redirect на `/auth/login?next={current_path}`

### 26.2 Inline form errors

```html
<input class="input" aria-invalid="true" aria-describedby="err-email">
<p id="err-email" class="text-sm text-[var(--danger)] mt-1">
  Email уже зарегистрирован
</p>
```

### 26.3 Undo toast

`_partials/undo_toast.html` — fixed bottom + animate-slide-up + auto-dismiss 5s.

---

## 27. HTMX patterns

### 27.1 Inline edit

```html
<span hx-get="/api/task/{id}/edit-inline" hx-trigger="dblclick" hx-swap="outerHTML">
  Title
</span>
```

### 27.2 Optimistic toggle

```html
<input type="checkbox" hx-post="/api/task/{id}/toggle"
       hx-target="closest li" hx-swap="outerHTML">
```

### 27.3 Infinite scroll

```html
<div hx-get="/api/tasks?cursor={last_id}" hx-trigger="revealed" hx-swap="afterend">
  Loading
</div>
```

### 27.4 Out-of-band swap

`hx-swap-oob="true"` для обновления sidebar counters.

### 27.5 Boost navigation

`<a hx-boost="true">` превращает navigation в HTMX swap.

---

## 28. Toast / notifications

### 28.1 Browser Notification API

Для reminders + Pomodoro. Permission запрос lazy.

### 28.2 Undo toast

После destructive action — toast с Undo + 5s auto-dismiss.

### 28.3 Permanent banner

`_partials/beta_banner.html`. Dismiss через `localStorage`.

---

## 29. Confetti / celebrations

При completion important task / streak / milestone:
```js
const stage = document.querySelector('.confetti-stage');
for (let i = 0; i < 60; i++) { ... }
```

CSS-keyframes `confetti-fall` уже в base.html.

---

## 30. Tooltips

- Простые через `title` атрибут (a11y)
- Кастомные через Alpine + `@mouseenter`/`@mouseleave`

---

## 31. Quick-add UX

### 31.1 Hotkey Q
Открывает quick-add modal (web).

### 31.2 NLP синтаксис (`app/quickadd/parser.py`)
- `купить молоко завтра` → due_at = tomorrow
- `!1`, `!2`, `!3`, `!4` → priority
- `@label`, `#project` → label/project

### 31.3 Search palette
`Ctrl/Cmd+K` → fuzzy search.

---

## 32. Sortable.js convention

```js
Sortable.create(el, {
  handle: '.drag-handle',
  animation: 150,
  ghostClass: 'opacity-50',
  onEnd: function(evt) {
    htmx.ajax('POST', '/api/reorder', {
      values: { from: evt.oldIndex, to: evt.newIndex },
      swap: 'none'
    });
  }
});
```

---

## 33. Onboarding

`_partials/onboarding_card.html`:
- Sticky card в `/app/today` после регистрации
- Emoji + headline + 3-step intro
- «Понятно» button → POST `/api/onboarding/dismiss`
- Flag в `localStorage` чтобы не показывать снова

---

## 34. Дополнения к чек-листу новой страницы

К §20:

- [ ] Empty state предусмотрен
- [ ] Loading state (htmx-indicator или skeleton)
- [ ] Error state (404, validation)
- [ ] Mobile swipe / gestures если применимо
- [ ] HTMX boost для navigation
- [ ] Sortable handle если списки переставляются
- [ ] Modal patterns (focus trap, Esc, overlay-click)
- [ ] Toast feedback после destructive actions
- [ ] HapticFeedback (Mini App)
- [ ] Tooltip + aria-label на icon-only кнопках

---

## 35. Версия v2

v2.0 — 2026-05-19. Добавлено 14 новых секций (22-34) после Playwright-обхода: gestures, sheets, loaders, empty/error/loading states, HTMX patterns, toasts, confetti, tooltips, quick-add, sortable convention, onboarding.

Источники для v2:
- `app/templates/miniapp/_base.html` lines 134-340 (swipe + sheet + transitions)
- `app/templates/_partials/*.html` (empty, undo_toast, onboarding_card, search_palette, shortcuts)
- `app/miniapp/static.py` (touch + sortable + haptic)
- Playwright observations of 18 страниц
