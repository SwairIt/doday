# Recipe: добавить Jinja-шаблон

## Где живут шаблоны

```
app/templates/
  base.html               # для public-страниц (лендинг, /auth/*, /privacy)
  app_base.html           # для /app/* (sidebar + topbar + bottom-nav)
  _partials/              # переиспользуемые куски, начинаются с _
  app/<page>.html         # /app/<page>
  auth/<page>.html        # /auth/<page>
  help/<page>.html        # /help/<page>
```

## Минимальный новый шаблон

```html
{% extends "app_base.html" %}
{% block title %}Заметки — Doday{% endblock %}
{% block view_title %}Заметки{% endblock %}
{% block content %}

<h1 class="text-3xl font-bold mb-4">Заметки</h1>

<div class="card p-6">
  <p class="text-[var(--text-muted)]">Здесь будут твои заметки.</p>
</div>

{% endblock %}
```

`{% extends "app_base.html" %}` даёт sidebar + topbar + bottom-nav и Yandex.Metrika.
`{% extends "base.html" %}` — голый shell для лендинга и auth-страниц.

## Регистрация view

В `app/views/router.py` (или соответствующем `app/<feature>/router.py`):

```python
@router.get("/app/notes", response_class=HTMLResponse)
async def notes_view(
    request: Request, user: RequiredUser, session: DbSession
) -> HTMLResponse:
    notes = await list_notes(session, user.id)
    return templates.TemplateResponse(
        request,
        "app/notes.html",
        {"notes": notes, "current_user": user, "current_view": "notes"},
    )
```

## JSON в HTML-атрибуте

**Только** через `|tojson|forceescape`:

```html
<div x-data="{ items: {{ items|tojson|forceescape }} }">
```

**Никогда** так:
```html
<!-- ✗ ЛОМАЕТСЯ — кавычки внутри JSON разрушают атрибут -->
<div x-data="{ items: {{ items|tojson|safe }} }">
```

Pre-commit поймает `|tojson|safe` без последующего escape — увидишь ошибку.

## Z-index ладдер

Чтобы модал перекрывал sidebar, sidebar перекрывал bottom-nav, и так далее — придерживайся:

| Слой | Z | Файл |
|---|---|---|
| Модал (новый проект, фильтр-эдитор, апгрейд) | `z-50` | `_partials/*_modal.html` |
| Поиск/Cmd-K палитра | `z-50` | `_partials/search_palette.html` |
| Sidebar drawer на мобиле | `z-40` | `_partials/sidebar.html` |
| Bulk-bar | `z-40` | `_partials/bulk_bar.html` |
| Sidebar overlay (затемнение под drawer'ом) | `z-[35]` | `_partials/sidebar.html` |
| Bottom-nav (mobile) | `z-30` | `_partials/mobile_nav.html` |
| Help-кнопка ?, mobile FAB | `z-30` | `_partials/help_drawer.html`, `app_base.html` |
| Sticky topbar | `z-20` | `_partials/topbar.html` |
| Dropdown в строке задачи (приоритет, проект) | `z-20` / `z-30` | `_partials/task_row.html` |
| Tooltip-карточки на graph.html | `z-10` | `app/graph.html` |

Если добавляешь новый floating-элемент — выбери уровень из таблицы, не выдумывай свой.

## Touch-targets

Кнопки на мобиле — минимум **36×36px**. Для иконочных кнопок:

```html
<button class="w-9 h-9 inline-flex items-center justify-center rounded-lg hover:bg-[var(--surface-2)] transition">
  <svg class="w-4 h-4" ...></svg>
</button>
```

`w-9 h-9` = 36px touch-target, иконка `w-4 h-4` = 16px по центру.

## Размер шрифта

Не используй `text-[Npx]` где N < 11 — плохо читается на мобиле. Pre-commit (warning, не error) предупредит.

Если намеренно нужен мелкий (PRO-badge, счётчик) — добавь suppression:
```html
{# lint-ignore-next-line: small-text — это PRO-badge #}
<span class="text-[10px] uppercase font-bold">PRO</span>
```

## HTMX

Шаблоны с `hx-get`/`hx-post` дают partial-update без full-page reload. Паттерн:

```html
<button
  hx-post="/htmx/tasks/{{ task.id }}/toggle"
  hx-target="#task-{{ task.id }}"
  hx-swap="outerHTML swap:160ms"
  class="..."
>...</button>
```

Эндпоинт в `app/views/htmx.py` (или `app/<feature>/router.py`) возвращает `templates.TemplateResponse(request, "_partials/task_row.html", {...})`.

## Alpine.js inline

Малая клиент-side логика — Alpine `x-data`. Большая — выноси в `_partials/<name>.html` или вообще `<script>` в `base.html`.

```html
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">...</div>
</div>
```

Если `<script>` в шаблоне начинает быть длиннее 60 строк — линтер предупредит. Подумай — может пора в отдельный partial.

## Доступность

- Каждая иконочная кнопка — `aria-label="..."` или `title="..."`
- `<input>` с `placeholder=" "` нуждается в видимом `<label>` или `aria-label`
- Цветовой контраст — Tailwind дефолты обычно ок, но не используй `text-[var(--text-muted)]` для важной инфы
