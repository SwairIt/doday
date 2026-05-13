# Doday — упрощение + команды

**Дата:** 2026-05-13
**Контекст:** После 10 дней разработки и публикации статьи (план `2026-05-12-miniapp-v2-parity-stats-polish.md` ✅) приложение разрослось до 38 модулей с lazy-фичами (geймификация, mood, habits, time-tracking, school-parsers, audience-режимы и т.п.). Юзер хочет **пивот к focused todo-апу с командной работой** — Todoist-style.

**3 цели:**
1. **Упростить** агрессивно — и визуально, и функционально.
2. Добавить **комментарии к задачам и подзадачам** (бэкенд готов, UI на Mini App дополнить).
3. Сделать **shared projects** с email-инвайтами (Todoist-стиль).

**Бот вне scope.** Polling сейчас сломан на хостинге, чиним webhook'ом отдельной фазой после launch'a.

---

# Архитектура: 4 фазы

Один проект, 4 последовательные фазы. Каждая — отдельный коммит/набор коммитов в master, безопасно деплоится по одному.

```
α  AGGRESSIVE CLEANUP       ~1.5–2 дня
β  UI REDESIGN              ~1.5 дня
γ  COMMENTS UI POLISH       ~2 часа
δ  TEAM COLLAB              ~3 дня
```

**Принципы:**

- **Бот вне scope.** Mini App открывается через chat menu кнопку, бот для UI не нужен.
- **Удаляем данные без церемоний.** Pre-cleanup tag + pg_dump до migration на случай восстановления; реальных юзеров мало.
- **`BETA_FREE_FOR_ALL` остаётся.** Команды без лимита на бете.
- **Light theme = default.** Тёмная — toggle.
- **Permissions: `owner | member`.** Без viewer/admin/billing-role.
- **Assignee** включён в δ как минорный feature.
- **Что НЕ делаем:** activity feed, realtime WebSocket sync, threaded replies, role-customization, billing-per-team. Follow-ups.

---

# Phase α — Aggressive cleanup

## Удаляемые модули

Директории `app/<module>/` полностью:

| Модуль | Что внутри |
|---|---|
| `gamification/` | XP-события, уровни, 16 ачивок, daily challenges |
| `mood/` | daily mood-entry, эмоции |
| `habits/` | привычки, habit completions |
| `time_tracking/` | time-логи на задачу |
| `company/` | standup widget (audience='company') |
| `user_templates/` | шаблоны типа «учебная неделя» |
| `custom_filters/` | сохранённые фильтры power-user |
| `calendar_feed/` | .ics-фид аккаунта |
| `links/` | external links на задачах |

## School-модуль — сужаем surface, код остаётся

Файлы в `app/school/` (`{models,service,schedule_service,router,schemas,holidays,subjects}.py`) **остаются**. Router в `main.py` **остаётся** mounted на `/api/school/*`. Скрываем только UI-surface:
- Виджет «today_schedule» (для audience='school') — удаляется
- Subject-chips в quickadd — удаляются
- Sidebar-item «Расписание» — удаляется

Когда у юзера появится РФ-прокси + токен дневника — отдельной фазой возвращаем UI через Settings-toggle «Подключить дневник».

## Audience-mode полностью удаляется

- `ALTER TABLE users DROP COLUMN audience`
- `app/auth/service.py::_starter_samples_for(audience)` → `_starter_samples()` — единые стартовые задачи
- Profile page: убираем audience-switcher
- Welcome-flow: 1 страница приветствия без выбора аудитории
- Sidebar: убираем audience-conditional items
- Mini App `/miniapp/me` — убираем audience-режим если есть

## Migration `2026_05_13_drop_lazy_modules.py`

```python
def upgrade():
    # FK cascade — порядок важен
    op.drop_table('user_achievements')
    op.drop_table('user_progress')
    op.drop_table('xp_events')           # gamification
    op.drop_table('habit_completions')
    op.drop_table('habits')
    op.drop_table('mood_entries')
    op.drop_table('time_logs')
    op.drop_table('user_templates')
    op.drop_table('custom_filters')
    op.drop_table('task_links')          # external links на задачах
    op.drop_column('users', 'audience')

def downgrade():
    raise NotImplementedError(
        "Aggressive cleanup is one-way; restore from pre-cleanup tag if needed."
    )
```

Перед миграцией: `pg_dump` на проде → `../doday-pre-α-cleanup.sql`, git tag `pre-α-cleanup` на HEAD.

## Routes / templates / partials

- `app/main.py` — убрать `from app.<module>.router import` + `include_router(...)` для всех 9 модулей.
- Удалить `app/templates/<feature>/*.html` для удаляемых модулей.
- Подчистить:
  - `app/templates/base.html` — sidebar-items / scripts для habits/mood/time-tracking/streaks
  - `app/templates/landing.html` — упоминания удалённых features
  - `app/templates/pricing.html` — то же
  - `app/templates/today.html` — `{% include %}` для habits/mood/streak/sprint widget
  - `app/templates/profile.html` — audience-switcher

## Тесты

Удаляем `tests/test_{gamification,mood,habits,time_tracking,standup,streak_chip,sprint_widget,calendar_feed,task_links,user_templates,custom_filters,subject_chips,today_by_subject,welcome_flow}.py` — ~150 тестов.

Тесты которые упоминают audience (`test_auth.py`, `test_profile.py`, `test_today.py`) — переписываем под новый flow.

## Documentation

- `MEMORY.md` (.claude) — обновить `project_pivot.md`: убрать упоминание audience-modes
- `PROGRESS.md` — добавить запись «α cleanup done»
- `CLAUDE.md` — убрать «AUDIENCE MODEL 2026-05-04» секцию

## Acceptance criteria α

- `git status` чистый, нет references на удалённые модули
- `uv run pre-commit run --all-files` green
- `uv run pytest -q` green (~480 тестов)
- `uv run alembic upgrade head` локально работает
- После deploy: `python scripts/smoke_test.py https://getdoday.ru` 23/23 green
- Manual: `/app/today`, `/app/inbox`, `/app/projects/<id>`, `/app/profile` рендерятся без 500
- `/miniapp/` открывается, не сломалось

---

# Phase β — UI redesign

## Палитра

**Light = default** везде (web + Mini App). Тёмная — toggle.

```
LIGHT (default):
  --bg            #fafafa   slate-50
  --surface       #ffffff   white
  --surface-2     #f1f5f9   slate-100
  --text          #0f172a   slate-900
  --text-muted    #64748b   slate-500
  --accent        #7c3aed   violet-600 (фирменный)
  --border        rgba(15,23,42,0.08)

DARK:
  переменные не трогаем, всё что есть остаётся.
```

Tailwind utility classes остаются `text-[var(--text-muted)]` — не переписываем каждый chip.

## Sidebar (web): 4 пункта вместо 8-10

```
🏠 Сегодня
📥 Инбокс
📅 Календарь   (объединили Upcoming + Calendar в одну страницу с tabs)
📁 Проекты    (раскрывается — список + кнопка «+ Новый»)
─────────
[+ Добавить]  (sticky-bottom quickadd)

[D] bugdenes@gmail.com  → /app/settings  (footer)
```

- Labels + Filters → переезжают в `/app/search` как side-фильтры.
- Profile + Settings → один экран `/app/settings`. Footer-row в sidebar = аватарка + email → click → settings.
- Sidebar collapsible на мобиле, fixed-width на desktop.

## Task row: одна строка

```
До:
┌──────────────────────────────────────────────────────────┐
│ [ ] [●] Сходить в зал завтра !!!  📌 @спорт #хобби 🔁    │
│         описание…                                        │
│         [3/5] подзадач   [P1]   через 6 дней             │
└──────────────────────────────────────────────────────────┘

После:
┌──────────────────────────────────────────────────────────┐
│ ○ Сходить в зал — спорт                  пт 14:00    ⋯  │
└──────────────────────────────────────────────────────────┘
```

- `○` — кружок-чекбокс, цвет рамки = priority (rose/amber/sky/slate)
- Title + em-dash + первый лейбл italic-muted (если есть)
- Дата справа compact (`завтра`, `пт 14:00`, `15 дек`)
- `⋯` — overflow-menu / открывает task-detail
- Pinned: 📌 микро-иконка перед title
- Recurrence/subtask-progress — скрыты в строке, видны в detail

## Settings — один экран `/app/settings`

Скролл-страница с 4 секциями:

```
ПРОФИЛЬ
   [D]   Ярослав
         bugdenes@gmail.com  [Изменить]
   [Сменить пароль]   [Выйти]

ВНЕШНИЙ ВИД
   Тема:       🌙 Тёмная  ☀️ Светлая  🖥 Системная
   Акцент:     Violet (по умолчанию)

УВЕДОМЛЕНИЯ
   Утренний дайджест в Telegram   [ ]
   Reminders по дедлайнам          [ ]

УЧЁТКА
   [Удалить аккаунт]
```

`/app/profile` redirect'ит на `/app/settings`. Старый sidebar-tab «Профиль» удаляется.

## Landing / Pricing / Onboarding

- `landing.html` — copy-edit: убрать упоминания удалённых features (habits, mood, gamification, school)
- `pricing.html` — оставить «Бета — всё бесплатно» card
- Onboarding (`/auth/register` → `/welcome`) — 1 экран: email+password → редирект сразу в `/app/today` со стартовыми задачами

## Mini App изменения

- Default theme = **light** (был dark). Inline-script в `<head>`: `localStorage.dodayTheme || 'light'`.
- `_partials/task_card.html` — убрать «висит N дн.», «3/5 подзадачи» из строки, перенести в task_sheet.
- Оставить chips для priority + due + recurrence, остальное скрыть.
- Bottom-nav — 5 табов остаются как сейчас.

## Templates touched

```
app/templates/base.html                           sidebar redesign
app/templates/_partials/task_row.html             one-line task
app/templates/_partials/sidebar.html              новый файл (extract)
app/templates/landing.html                        copy + design cleanup
app/templates/pricing.html                        прощание lazy-table
app/templates/today.html                          убрать удаляемые виджеты
app/templates/profile.html                        → settings.html (merge)
app/templates/welcome.html                        1-step instead of 3

app/templates/miniapp/_base.html                  default light theme
app/templates/miniapp/_partials/task_card.html    simplify chips
```

## Acceptance criteria β

- Light theme = default на свежем юзере (web + miniapp). Toggle работает в обе стороны.
- Sidebar web — 4 main items + projects + footer.
- Task row — одна строка, переполнения нет на 1280px ширине.
- Settings — один экран, без табов.
- Pre-commit + pytest + smoke 23/23 green.
- Manual: визуально clean, нет лишних chips/эмодзи в task-list.

---

# Phase γ — Comments UI polish

## Backend уже работает

`app/comments/router.py` mounted в `main.py` через `task_comments_router` + `comments_router`. Endpoints:
- `GET /api/tasks/{task_id}/comments` — list (newest first)
- `POST /api/tasks/{task_id}/comments` — create, body in JSON
- `PATCH /api/comments/{comment_id}` — update body (author only)
- `DELETE /api/comments/{comment_id}` — delete (author only)

Auth через `RequiredUser` (cookie-session) — работает и для web, и для Mini App.

**Subtasks** — comments автоматически работают (FK на `tasks.id`, подзадача = строка в `tasks`).

## Web — task-detail

Если accordion для комментариев на `/app/tasks/<id>` уже есть — подкручиваем под light-тему. Если нет — добавляем простой блок:

```
КОММЕНТАРИИ (3)
─────────────────────────────────────
 Я · 5 минут назад
 Готово, выложил в общий чат. ✓     ⋯
─────────────────────────────────────
 Аня · вчера
 Тесты проходят, проверю утром.
─────────────────────────────────────

┌─────────────────────────────────────┐
│ Написать комментарий…               │
└─────────────────────────────────────┘
                  [Ctrl+↵] [Отправить]
```

## Mini App — `task_sheet.html`

Accordion между «Описание» и «Подзадачи», collapsed по умолчанию:

```
💬 Комментарии · 3       ▼
─────────────────────────────
 список + Input + ➤
```

Alpine state:

```javascript
{
  comments: [],
  open: false,
  body: '',
  
  async load() {
    const r = await fetch(`/api/tasks/${task.id}/comments`, {credentials: 'include'});
    if (r.ok) this.comments = await r.json();
  },
  async add() {
    if (!this.body.trim()) return;
    await fetch(`/api/tasks/${task.id}/comments`, {
      method: 'POST',
      credentials: 'include',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({body: this.body}),
    });
    this.body = '';
    await this.load();
  },
  async del(id) {
    await fetch(`/api/comments/${id}`, {method: 'DELETE', credentials: 'include'});
    await this.load();
  }
}
```

`load()` срабатывает при первом раскрытии accordion.

## Acceptance criteria γ

- Web: на `/app/tasks/<id>` accordion «Комментарии», добавить/удалить/edit работает
- Mini App: в `task_sheet` accordion «Комментарии», fetch ленивый, добавление/удаление работает
- Subtasks: открыть subtask в task_sheet → его comments отдельные от parent'a
- Pre-commit + pytest + smoke 23/23 green

---

# Phase δ — Team collab (shared projects)

## DB schema

### `project_members` (новая таблица)

```python
class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
        Index("ix_project_members_user_id", "user_id"),
    )

    id: UUID = primary_key
    project_id: UUID = FK("projects.id", ondelete="CASCADE")
    user_id: UUID = FK("users.id", ondelete="CASCADE")
    role: str = Mapped[str]  # 'owner' | 'member'
    joined_at: datetime
```

При создании проекта автоматически добавляется row `(project_id, user_id=owner, role='owner')`. Backfill для existing projects: на каждого `projects.user_id` создать owner-row.

### `project_invitations` (новая таблица)

```python
class ProjectInvitation(Base):
    __tablename__ = "project_invitations"
    __table_args__ = (
        UniqueConstraint("project_id", "invitee_email", "status"),
        Index("ix_project_invitations_token", "token"),
        Index("ix_project_invitations_email", "invitee_email"),
    )

    id: UUID = primary_key
    project_id: UUID = FK("projects.id", ondelete="CASCADE")
    inviter_id: UUID = FK("users.id", ondelete="CASCADE")
    invitee_email: str  # lowercased
    token: str  # secrets.token_urlsafe(32), unique
    expires_at: datetime  # +7 days
    status: str  # 'pending' | 'accepted' | 'revoked'
    accepted_at: datetime | None
    created_at: datetime
```

### `tasks.assigned_to` (новое поле)

```python
assigned_to: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", ondelete="SET NULL"), nullable=True
)
```

При assign — проверка что user — member of `task.project_id`.

## Service layer

### `app/projects/service.py` (новые функции)

- `list_members(session, project_id) -> list[ProjectMember]`
- `add_member(session, project_id, user_id, role='member')` — idempotent
- `remove_member(session, project_id, user_id)` — owner remove'нуть себя нельзя
- `is_member(session, project_id, user_id) -> bool` — кэшировать в request-scope если нужно
- `is_owner(session, project_id, user_id) -> bool`

### `app/projects/invitations_service.py` (новый файл)

- `create_invitation(session, project_id, inviter_id, invitee_email) -> ProjectInvitation`
  - lowercase email
  - check inviter is owner of project
  - check invitee не уже member
  - check inviter не invitee
  - generate token, expires_at = utcnow + 7d
  - status='pending'
  - send email с link `https://getdoday.ru/invite/<token>`
- `accept_invitation(session, token, user_id) -> Project`
  - find by token + status='pending' + not expired
  - check user.email matches invitee_email (или allow if logged-in user)
  - create `project_members` row
  - mark invitation status='accepted', accepted_at=utcnow
  - return project
- `revoke_invitation(session, invitation_id, requester_id)`
  - check requester is owner
  - mark status='revoked'

## Permission middleware

Каждый запрос на `task_id` / `project_id` / `section_id` / `comment_id` проверяет membership.

Вспомогательный dependency:

```python
async def require_project_access(
    project_id: UUID, user: RequiredUser, session: DbSession
) -> Project:
    project = await get_project(session, project_id)
    if project is None:
        raise HTTPException(404)
    if not await is_member(session, project_id, user.id):
        raise HTTPException(403)
    return project


async def require_project_owner(...) -> Project:
    # как require_project_access + check role='owner'
```

Existing endpoints в `app/projects/router.py`, `app/tasks/router.py`, `app/sections/router.py`, `app/comments/router.py` — обновляем чтобы они проверяли membership вместо просто owner-check.

Migration owner-check → member-check для **существующих** endpoints — критично. Я перечислю все endpoints в плане implementation.

## Email invitations

Letter рендерится через Jinja template `app/templates/email/invitation.html`:

```
Тема: Тебя пригласили в проект «Учебная неделя» на Doday

Привет!

Ярослав (bugdenes@gmail.com) приглашает тебя в проект «Учебная неделя»
на Doday — это совместный to-do list.

[ Принять приглашение ]
(ссылка действует 7 дней)

Если ты не знаешь Ярослава — просто проигнорируй это письмо.
```

Используем existing SMTP-инфраструктуру (`aiosmtplib`).

## UI changes

### `/app/projects/<id>` — «Поделиться» button

```
┌─────────────────────────────────────────┐
│ Учебная неделя               🔗 Поделиться │
└─────────────────────────────────────────┘
```

Клик → modal:

```
┌─────────────────────────────────────────┐
│ Поделиться проектом «Учебная неделя»    │
│                                         │
│  Email участника:                       │
│  ┌──────────────────────┐               │
│  │ anya@example.com     │               │
│  └──────────────────────┘               │
│                       [Пригласить]      │
│                                         │
│  ─────────────────────────────────      │
│                                         │
│  Уже в проекте:                         │
│  [Я] Ярослав              (владелец)    │
│  [А] Аня (anya@…)         🗑            │
│                                         │
│  Pending инвайты:                       │
│  saша@yandex.ru           ↺ revoke      │
└─────────────────────────────────────────┘
```

### `/invite/<token>` page

- Если юзер не залогинен → редирект на `/auth/login?next=/invite/<token>` (после login возврат)
- Если email юзера совпадает с invitee_email — `Accept` кнопка
- Если email не совпадает — сообщение «Приглашение для другого email, проверь ссылку»
- Accept → create membership → redirect на `/app/projects/<id>`

### Task — assignee selector

В task-detail (web + mini app task_sheet) — селектор «Назначить»:

```
Назначено: [Аня ▼]
            └── Список members проекта
```

Если задача в проекте «Inbox» (один юзер) — селектор скрыт.

## API endpoints (новые)

```
GET    /api/projects/{id}/members              list
POST   /api/projects/{id}/invites              create invitation
GET    /api/projects/{id}/invites              list pending invitations (owner only)
DELETE /api/invites/{invitation_id}            revoke (owner only)
DELETE /api/projects/{id}/members/{user_id}    remove member (owner only)

POST   /invite/{token}                          accept invitation (auth required)
GET    /invite/{token}                          render accept-page
```

## Tests

- `test_project_members.py` — add/remove/is_member/is_owner
- `test_project_invitations.py` — create/accept/revoke/expiry
- `test_project_permissions.py` — non-member получает 403 на task/comment/section CRUD
- `test_task_assignee.py` — assigned_to FK + member-check

~30 новых тестов.

## Migrations

1. `2026_05_13_create_project_members.py` — таблица + backfill (для каждого projects: owner-row)
2. `2026_05_13_create_project_invitations.py` — таблица
3. `2026_05_13_tasks_assigned_to.py` — `ALTER TABLE tasks ADD COLUMN assigned_to UUID NULL`

## Acceptance criteria δ

- `project_members` + `project_invitations` таблицы созданы, backfill сработал для existing проектов
- Owner может invite by email, letter приходит, link открывает accept-page
- Non-member получает 403 на все project/task/section/comment endpoints
- Non-member project не виден в sidebar
- Member может create/edit/complete tasks + comments
- Owner может remove member; revoke pending invitation
- Assignee field работает в web + miniapp, только member может быть assignee
- Email letter готов на Jinja-template, SMTP работает на проде
- ~30 новых тестов green, 0 регрессий в existing

**Estimate δ: 3 дня.**

---

# Общие принципы реализации

1. **Каждый чанк → отдельный commit + push.** Cron-poll deploy 60s после push.
2. **Pre-commit обязательно green** (ruff + mypy strict + jinja-linter) перед commit'ом.
3. **pytest -q green** после каждого чанка.
4. **Smoke 23/23** на проде после deploy.
5. **Russian past-tense commits**, author `112168281+SwairIt@users.noreply.github.com`.
6. **Backup перед миграциями**: `pg_dump` + git tag.
7. **NO breaking changes для существующих юзеров** (после α-cleanup).
8. **Документация** обновляется в каждом чанке (PROGRESS.md, CLAUDE.md где требуется).

---

# Связь с предыдущими планами

- `2026-05-11-habr-launch-and-miniapp.md` ✅ закрыт (mini-app v1 функционален)
- `2026-05-12-miniapp-v2-parity-stats-polish.md` ✅ закрыт (parity + stats + polish)
- `2026-05-11-miniapp-imba.md` — частично закрыт (α-θ фазы имба-mode)
- **Этот план** заменяет «доделать η-фазу с notes/comments» и идёт дальше — comments на Mini App теперь часть γ, а после α/β много существующего кода удалится.
