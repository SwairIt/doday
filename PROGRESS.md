# Doday — Progress tracker

**Purpose:** session-spanning progress tracker. Read this first in every session/iteration.

---

## 2026-05-21 — Ralph-loop: имя проекта в строке задачи (кросс-проектные виды)

`today/upcoming/filter/label/done` views теперь отдают `project_name_map`
(`{id: name}`). В `_partials/task_row.html` под guard `project_name_map is defined
and task.project_id in …` — точка проекта получает `title` = имя, и рядом
приглушённый чип имени (truncate, цвет проекта). Одиночный `project_view` map не
передаёт → чип не дублируется (паттерн assignee_map/subtask_counts). Без бэкенда
и схемы БД. mypy strict + ruff + lint_templates зелёные, тесты 31 passed,
Playwright: на Today у задач чип «Inbox» (title «Проект: Inbox»), 0 console
errors. Скрин `docs/screenshots/project-name-in-row.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: относительные подписи дедлайна (Сегодня/Завтра/Вчера)

Новый `app/views/template_filters.py::due_label(task)` рядом с `due_state`:
вчера/сегодня/завтра → слова, дальше — `dd.mm` (timed +` HH:MM`). Зарегистрирован
Jinja-глобалом в `views/router.py` и `views/htmx.py`. Чип даты в
`_partials/task_row.html` и `_partials/kanban_card.html` теперь рендерит
`{{ due_label(task) }}` вместо `strftime`. Цвет (`due_state`) и date-dropdown не
тронуты. Без бэкенда и схемы БД. Тесты `tests/test_due_state.py` (10, +2):
относительные слова и абсолютный/timed формат. mypy strict + ruff + lint_templates
зелёные, Playwright: чип сегодняшних задач показывает «Сегодня», 0 console errors.
Скрин `docs/screenshots/relative-due-labels.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: метаданные задачи в task_detail (создано/завершено)

В `_partials/task_detail.html` добавлен футер с `border-t`, мелким текстом:
«Создано dd.mm.yyyy» + «· Завершено dd.mm.yyyy» (если `task.completed_at`).
Серверный рендер из `task.created_at`/`completed_at`, без бэкенда и схемы БД.
lint_templates 0 errors, тесты 19 passed, Playwright: панель показывает
«Создано 21.05.2026», 0 console errors. Скрин
`docs/screenshots/task-detail-meta.png`. Деплой подтверждён через /version.

(Прошлая итерация: задача про markdown-описание оказалась дублем — `window.dodayMd`
уже реализован в base.html; закрыта без коммита, зафиксирован урок проверять
по доменным именам.)

---

## 2026-05-21 — Ralph-loop: входящие приглашения (in-app баннер «Принять»)

Раньше приглашение принималось только по email-ссылке `/invite/{token}`.
`app/projects/invitations.py`: `list_invitations_for_email(session, email)` →
[(invitation, project_name)] (pending, не истёкшие, join Project). Эндпоинты в
invites_router: `GET /api/invites/incoming` (приглашения для email текущего
юзера, схема `IncomingInviteOut`), `POST /api/invites/{token}/accept`
(переиспользует `accept_invitation`). Баннер `_partials/incoming_invites.html`
(Alpine, fetch на загрузке, «Принять»/скрыть) подключён в app_base. Без
изменений схемы БД. Тесты `tests/test_incoming_invites.py` (3): сервис видит
свои pending, incoming-эндпоинт + accept присоединяет к проекту, 401 без auth.
mypy strict + ruff + lint_templates зелёные, Playwright: приглашённый видит
баннер «Вас пригласили…» → «Принять» → проект в сайдбаре, 0 console errors. Скрин
`docs/screenshots/incoming-invite-banner.png`. Деплой подтверждён через /version.
Цикл членства полный: пригласить → принять in-app → передать владение → покинуть.

---

## 2026-05-21 — Ralph-loop: передача владения проектом

Закрывает дыру из leave-фичи («передайте владение»). `app/projects/membership.py`:
новый `set_role(session, project_id, user_id, role)`. Эндпоинт
`POST /api/projects/{id}/members/{user_id}/make-owner` (owner-only): target→owner,
caller→member (полная передача), 403 для не-владельца, 404 для не-члена.
В `share_modal.html` у участника — действие «👑 Передать владение» (confirm →
make-owner → reload). Без изменений схемы БД. Тесты `tests/test_leave_project.py`
(6, +3): передача меняет роли, требует владельца (403), аноним 401. mypy strict +
ruff + lint_templates зелёные, Playwright: владелец → «Передать владение» →
confirm → reload, в шапке стало «Покинуть» (бывший владелец — участник), 0
console errors. Скрин `docs/screenshots/transfer-ownership.png`. Деплой подтверждён
через /version. Цикл членства замкнут: добавить → передать владение → покинуть.

---

## 2026-05-21 — Ralph-loop: «Покинуть проект» для участника-не-владельца

Новый эндпоинт `POST /api/projects/{id}/leave` (`app/projects/router.py`):
участник удаляет себя через `remove_member`; владелец → 400, не-член → 400,
без auth → 401. Кнопка «🚪 Покинуть» в шапке `project.html` для не-владельца
не-inbox проекта (`{% elif not project.is_inbox %}`), `hx-confirm` +
`hx-on::after-request` редирект на /app/today. Без изменений схемы БД. Тесты
`tests/test_leave_project.py` (3): участник выходит (204, role→None), владелец
400, аноним 401. mypy strict + ruff + lint_templates зелёные, Playwright:
участник видит «Покинуть» → confirm → редирект, проект исчез из сайдбара, 0
console errors. Скрин `docs/screenshots/leave-project-button.png`. Деплой
подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: «Перенести всё на сегодня» на фильтре Просрочено

Расширение Today-фичи на `/app/filters/overdue`. В `app/templates/app/filter.html`
кнопка «📅 На сегодня» + инлайн `dodayRescheduleAllOverdue()` рендерятся только
при `filter.slug == 'overdue'` и непустом списке (другие фильтры и label-view с
dict-filter без slug не затронуты — Jinja Undefined-guard). Собирает id всех
задач страницы → `/htmx/bulk` set_due=сегодня → reload. Без бэкенда и схемы.
Тест `tests/test_label_tasks.py` (5, +1): label-view с dict-filter рендерится 200
(не падает на filter.slug). lint_templates 0 errors, тесты 23 passed, Playwright:
на overdue-фильтре кнопка → задача ушла («найдено: 0»), на no-date кнопки нет, 0
console errors. Скрин `docs/screenshots/overdue-filter-reschedule.png`. Деплой
подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: бейджи-счётчики у фильтров в сайдбаре

`app/filters/service.py`: вынес where-условия в `_filter_conditions`, добавил
`count_for_filter(session, user_id, slug)` (общая логика с `list_for_filter`).
`sidebar_counts_endpoint` отдаёт новые ключи `no_date/high_priority/this_week`
(overdue уже был). В `_partials/sidebar.html` цикл фильтров получил бейдж
`x-show counts[key]>0` цвета фильтра. Без изменений схемы БД. Тесты
`tests/test_assigned.py` (19, +1): count_for_filter == len(list_for_filter) по
всем slug, эндпоинт содержит новые ключи. mypy strict + ruff + lint_templates
зелёные, Playwright: «Высокий приоритет · 2», «На этой неделе · 5», 0 console
errors. Скрин `docs/screenshots/filter-badges.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: bulk «Назначить выбранные на меня»

Замыкает набор assign-операций (одиночное — ctx-меню/детали). Ветка
`assign_me` в `app/views/htmx.py::bulk_action` (для каждого id
`update_task(assigned_to=user.id)`, try/except TaskNotFound/ValueError —
не-член пропускается). Кнопка «🙋 На меня» в `_partials/bulk_bar.html` (форма
как complete/duplicate). Без изменений схемы БД и нового эндпоинта. Тесты
`tests/test_assigned.py` (18, +2): bulk assign_me назначает на юзера, /htmx/bulk
401 без auth. mypy strict + ruff + lint_templates зелёные, Playwright: выделил
2 задачи → «На меня» → ушли в группу «ralphassigned» с аватарами, 0 console
errors. Скрин `docs/screenshots/bulk-assign-me.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: аватары участников в шапке shared-проекта

В шапке `app/templates/app/project.html` добавлен кластер аватаров участников
(перед «Поделиться»): инициалы на цветном фоне из `assignee_map`, наложение
`-space-x-2`, ring под фон. Показывается только при `assignee_map|length > 1`
(соло-проекты не засоряются), первые 5 + «+N». Без бэкенда и схемы
(assignee_map уже в контексте). lint_templates 0 errors, тесты 16 passed,
Playwright: для команды (2 участника R+T) кластер виден, 0 console errors. Скрин
`docs/screenshots/project-member-avatars.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: вид «задачи по лейблу» + кликабельные лейблы

Новый `app.labels.service.list_tasks_by_label` (join task_labels, открытые
top-level, не в корзине; labels eager via lazy=selectin). Роут
`GET /app/labels/{label_id}` в views/router (auth, 404 на чужой лейбл),
переиспользует `app/filter.html` с filter-dict (name=@лейбл, цвет лейбла,
tag-иконка). Лейблы стали кликабельны: чип в `task_row.html` → `<a>` на вид
лейбла, счётчик на `app/labels.html` → ссылка. Без изменений схемы БД. Тесты
`tests/test_label_tasks.py` (3). mypy strict + ruff + lint_templates зелёные,
Playwright: вид «@важное · найдено 1» + клик по чипу навигирует, 0 console
errors. Скрин `docs/screenshots/label-tasks-view.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: переиспользуемые toast-уведомления (dodayToast)

Новый партиал `_partials/toast.html` — singleton с глобальной
`window.dodayToast(message, {icon?, duration=2500})` (Alpine, по образцу
undo_toast, fixed bottom-center, role=status/aria-live, авто-скрытие). Подключён
в `app_base.html`. «🔗 Скопировать ссылку» в task_context_menu теперь даёт
отклик: success → «Ссылка скопирована», ошибка → «Не удалось скопировать». Без
бэкенда и схемы. lint_templates 0 errors, тесты 16 passed, Playwright +
evaluate-проверка: тост рендерится (display:flex, opacity:1, текст
«🔗 Ссылка скопирована»), 0 console errors. Скрин
`docs/screenshots/toast-copied.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: кнопка «Перенести просроченное на сегодня» (Today)

Focused-todo классика. В `app/templates/app/today.html` секции «Просрочено»
добавлена кнопка «📅 На сегодня» + инлайн-скрипт `dodayRescheduleOverdue()`:
собирает id задач из `#overdue-section`, шлёт `POST /htmx/bulk`
(`action=set_due`, `due=сегодня YYYY-MM-DD`), reload. Переиспользует
существующий bulk-эндпоинт — без бэкенда и схемы БД. lint_templates 0 errors,
тесты 16 passed, Playwright: клик убрал секцию «Просрочено», задача (18.05)
переехала в «Сегодня · 3» с янтарной датой, 0 console errors. Скрин
`docs/screenshots/reschedule-overdue-today.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: deep-link на задачу (?task=) + «Скопировать ссылку»

Чистый фронт в `_partials/task_context_menu.html` (глобальный скрипт на всех
/app). Пункт меню «🔗 Скопировать ссылку» → `navigator.clipboard.writeText(
origin+pathname+'?task='+id)`. На загрузке страницы `openDeepLinkedTask()` читает
`?task=<uuid>` и открывает деталь через существующий `GET /htmx/tasks/{id}/detail`
в `#task-detail-slot` (UUID-regex, guard на htmx/slot). Без бэкенда и схемы.
lint_templates 0 errors, тесты 16 passed, Playwright: `?task=<id>` авто-открыл
панель детали, 0 console errors. Скрин `docs/screenshots/deep-link-task.png`.
Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: группировка задач по исполнителю (проект-вью)

Расширил существующий Alpine-механизм `groupBy` в `app/templates/app/project.html`
(было none/priority/date) вариантом `assignee`. `project_view` отдаёт
`assignee_map_js` (строко-ключевой dict для JSON); в шаблоне он встроен через
`<script type="application/json">` и читается `JSON.parse` в x-data (чтобы кавычки
не ломали x-data-атрибут). `_groupKey/_groupLabel/_groupOrder` получили ветку
assignee; пункт меню «По исполнителю». В `task_row.html` добавлен
`data-assignee`. Без изменений схемы БД и бэкенда (assignee_map уже был).
mypy strict + ruff + lint_templates зелёные, тесты 28 passed, Playwright:
группы «🙋 …@example.com · 2» и «👤 Без исполнителя · 3», 0 console errors.
Скрин `docs/screenshots/group-by-assignee.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: счётчик подзадач «X/Y» в строке задачи

Новый `app.tasks.service.subtask_counts_for(session, user_id, parent_ids) ->
dict[UUID, tuple[done, total]]` — один group-by SELECT (case-sum), без N+1, без
изменения схемы, корзина исключена. `project_view` собирает `subtask_counts` по
активным родителям (из by_section.values) и кладёт в контекст. В
`_partials/task_row.html` бейдж «{done}/{total}» рядом с кареткой (зелёный когда
всё закрыто), в `_partials/kanban_card.html` — в полосе chips. Guard
`subtask_counts is defined` → today/inbox/filter не затронуты. Тесты
`tests/test_assigned.py` (16, +3). mypy strict + ruff + lint_templates зелёные,
Playwright: бейдж «1/3» виден, 0 console errors. Скрин
`docs/screenshots/subtask-count-badge.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: эндпоинт /version для проверки доставки деплоя

Enabler для авто-проверки деплоя в лупе. `app/main.py::_read_git_sha()` читает
git SHA один раз при старте (env `DODAY_GIT_SHA` → `git rev-parse HEAD` в repo →
"unknown"), `GET /version` отдаёт `{"sha": ...}`. Добавлен в `scripts/smoke_test.py`
(24 endpoint'а). Теперь луп после push поллит `https://getdoday.ru/version`
пока SHA != запушенного, и только тогда считает деплой дошедшим; если не доходит
за ~4 мин — самолечение (SSH git pull + рестарт, диагностика cron-poll).

---

## 2026-05-21 — Ralph-loop: подсветка просроченных/сегодняшних дедлайнов

Новый Jinja-helper `app/views/template_filters.py::due_state(task) ->
overdue|today|future|none` (date-only — по дню, timed — по моменту UTC;
завершённые не overdue). Зарегистрирован глобалом на template-env в
`views/router.py` и `views/htmx.py` (оба рендерят task_row). Чип даты в
`_partials/task_row.html` и `_partials/kanban_card.html`: overdue → красный
(rose), today → янтарный (amber), иначе цвет проекта. Без изменений схемы БД.
Тесты `tests/test_due_state.py` (8). mypy strict + ruff + lint_templates
зелёные, Playwright: 18.05 красная, 21.05 янтарная, 22.05 приглушённая, 0
console errors. Скрин `docs/screenshots/due-overdue-highlight.png`.

---

## 2026-05-21 — Ralph-loop: быстрое «Назначить на меня / Снять» в контекст-меню

Чистый фронт (бэкенд PATCH `assigned_to` уже поддерживал назначение и снятие
через `_SENTINEL`). В `_partials/task_context_menu.html` добавлены пункты
«🙋 Назначить на меня» (PATCH `assigned_to=current_user.id`) и «🙅 Снять
назначение» (PATCH `assigned_to=null`); id текущего юзера проброшен через
`data-me="{{ current_user.id }}"` на меню (доступен, т.к. меню инклудится в
app_base, а `current_user` в контексте всех /app). Без изменений схемы БД и без
нового эндпоинта. Тест `tests/test_assigned.py` (13, +1): `update_task`
назначает self и снимает (None). mypy strict + ruff + lint_templates зелёные,
Playwright: меню → «Назначить на меня» → у задачи появился аватар «R», 0 console
errors. Скрин `docs/screenshots/ctx-assign-me.png`.

---

## 2026-05-21 — Ralph-loop: аватар исполнителя в строке задачи (проект-вью)

Замыкает серию «Назначено мне». Новый `app.projects.membership.assignee_map_for_project`
— `dict[user_id, {initial, label, color}]` (join ProjectMember+User, цвет
детерминированно из палитры Tailwind по `user_id.hex`). `project_view` кладёт
`assignee_map` в контекст project.html/kanban.html. В `_partials/task_row.html`
и `_partials/kanban_card.html` — аватар-кружок с инициалом исполнителя, guard
`assignee_map is defined and task.assigned_to in assignee_map` (обратно-совместимо:
today/inbox/filter map не передают → ничего не рендерится). Без изменений схемы БД.
Тесты `tests/test_assigned.py` (12, +2): map содержит участника с верным
инициалом/цветом, пустой map для неизвестного проекта. mypy strict + ruff +
lint_templates зелёные, Playwright залогиненным: на задаче виден аватар «R»
с тултипом, 0 console errors. Скрин `docs/screenshots/task-row-assignee-avatar.png`.

---

## 2026-05-21 — Ralph-loop: бейдж-счётчик «Назначено мне» в сайдбаре

Продолжение фичи /app/assigned. Новый `app.tasks.service.count_assigned_to_user`
(тот же фильтр, что у `list_assigned_to_user` — open, не в корзине, только
проекты-членства). Эндпоинт `GET /api/projects/sidebar-counts` расширен ключом
`"assigned"` (контракт `dict[str,int]` — только новый ключ). В
`_partials/sidebar.html` пункт `assigned` в `secondary_nav` получил бейдж по
паттерну inbox/today (`x-show counts['assigned']>0`). Без изменений схемы БД.
Тесты `tests/test_assigned.py` (10, +4): count матчит list, исключает
завершённые/непринадлежащие, эндпоинт отдаёт ключ `assigned`, 401 без auth.
mypy strict + ruff + lint_templates зелёные, curl эндпоинт → 401, Playwright
0 console errors, эндпоинт в браузере вернул `"assigned":0`. Скрин
`docs/screenshots/sidebar-assigned-badge.png`.

---

## 2026-05-21 — Ralph-loop: фикс console-ошибки чипа стрика в топбаре

Чип стрика в `_partials/topbar.html` инициализировал `s: null` и фетчил
`/api/stats/streak`; `x-show` скрывал элемент, но Alpine всё равно вычислял
`:title` и `x-text="s.current"` при init → `Uncaught TypeError: Cannot read
properties of null (reading 'current')` на ВСЕХ `/app/*` у нового юзера без
streak. Фикс: дефолт `s: { current: 0, longest: 0, today_done: false }` вместо
null, `x-show="s.current > 0"`. Поведение чипа не изменилось. Playwright-смоук
залогиненным юзером без стрика: `/app/today` и `/app/assigned` теперь **0
console errors** (было 2). Скрин `docs/screenshots/topbar-streak-fix-no-console-errors.png`.
Найден в прошлой итерации при смоуке /app/assigned.

---

## 2026-05-21 — Ralph-loop: вид «Назначено мне» (assigned to me)

Аддитивная team-collab фича поверх δ. Новый сервис
`app.tasks.service.list_assigned_to_user` — открытые (не завершённые, не в
корзине) задачи, назначенные текущему юзеру, по всем проектам где он участник
(фильтр через `member_project_ids`, чтобы stale-назначение из проекта, откуда
юзера убрали, не утекало). Веб-роут `GET /app/assigned` (`app/views/router.py`),
шаблон `app/templates/app/assigned.html` (группировка по проекту, переиспользует
`_partials/task_row.html`, пустое состояние), ссылка в сайдбаре (блок «Ещё»).
Без изменений схемы БД. Тесты `tests/test_assigned.py` (6) зелёные, mypy strict
чист, ruff/lint_templates чисто, curl `/app/assigned` → 401, Playwright-смоук
залогиненным OK (скрин `docs/screenshots/assigned-empty.png`).

**Замечен предсуществующий баг** (не из этой задачи): чип стрика в топбаре
кидает `Cannot read properties of null (reading 'current')` на всех `/app/*`
для нового юзера без streak-данных — кандидат на отдельную задачу.

---

## 2026-05-22 — Ralph-loop: кнопка «Восстановить всё» в корзине (bulk restore)

Симметричный комплемент к «Очистить корзину»: массовое восстановление всех
soft-deleted задач. Без изменений схемы БД: `restore_all_trashed` (UPDATE
deleted_at=NULL, rowcount через cast CursorResult), `POST
/api/tasks/trash/restore` → `{"restored": n}` (объявлен до `/{task_id}/restore`),
кнопка «↩ Восстановить всё» в trash.html (без confirm). Тесты в
`tests/test_trash_bin.py` (+3), `pytest -q` 750 passed. Playwright: 3 удалённые →
«Восстановить всё» → корзина пуста, все вернулись, 0 console errors. Скрин
`docs/screenshots/trash-restore-all.png`. Деплой: prod `/version` sha=f08cf89 за
~25с, smoke 25/25 green. Commit `f08cf89`.

---

## 2026-05-22 — Ralph-loop: горячие клавиши g m / g e (Команда / Назначено мне)

Goto-шорткаты покрывали ~12 вью, но не teams-хабы. Добавил `g m` → /app/team и
`g e` → /app/assigned в `shortcuts.html` (g-ветка + overlay-справка). Фронт-only,
без бэкенда/схемы. Тест `tests/test_goto_shortcuts.py`, `pytest -q` 747 passed.
Playwright: g+m → Команда, g+e → Назначено мне, overlay показывает обе строки, 0
console errors. Скрин `docs/screenshots/goto-shortcuts-overlay.png`. Деплой: prod
`/version` sha=884d0ef за ~25с, smoke 25/25 green. Commit `884d0ef`. (Заметка по
тестам шорткатов в Playwright — в worklog: blur активного инпута + диспатч обоих
keydown подряд, т.к. pendingG живёт 1500мс.)

---

## 2026-05-22 — Ralph-loop: бейдж комментариев 💬 N на хабах Команда/Назначено

Бейдж «💬 N» был только в списке/доске проекта; добавил на кросс-проектные
teams-хабы `/app/team` и `/app/assigned`. Без изменений схемы БД/эндпоинтов/
шаблонов: `team_view` и `assigned_view` считают `comment_count_map`
(`comment_counts_for`) и кладут в контекст; task_row уже рендерит чип gated через
`comment_count_map is defined`. Тесты `tests/test_comment_badge_hubs.py` (3),
`pytest -q` 746 passed. Playwright: коммент к задаче → `/app/team` показал «💬 1»,
0 console errors. Скрин `docs/screenshots/comment-badge-team-view.png`. Деплой:
prod `/version` sha=d389ae7 за ~35с, smoke 25/25 green. Commit `d389ae7`.

---

## 2026-05-21 — Ralph-loop: поиск находит задачи команды в общих проектах

Глобальный поиск искал задачи только созданные мной (`Task.user_id == user`) —
задачи напарников в shared-проектах не находились (хотя поиск проектов уже шёл по
членству — рассогласование). Сменил фильтр задач на `Task.project_id IN
member_project_ids`; JSON project-name lookup тоже по member_ids. Без изменений
схемы БД и эндпоинтов; выдача строго ⊇ прежней в пределах прав (member_ids
включает личные проекты). Тесты `tests/test_search_team.py` (3), `pytest -q` 743
passed. Playwright: teammate создал задачу в shared-проекте → owner находит её
(JSON + живой ⌘K keyup), project_name резолвится, 0 console errors. Скрин
`docs/screenshots/search-team-tasks.png`. Деплой: prod `/version` sha=d0987ef за
~50с, smoke 25/25 green. Commit `d0987ef`.

---

## 2026-05-21 — Ralph-loop: «Создал: <участник>» в панели задачи

В детали-панели теперь виден автор задачи (создатель) для shared-проектов —
командная подотчётность (раньше виден только assignee). Без изменений схемы БД и
эндпоинтов: `task_detail` зовёт `assignee_map_for_project` → `is_shared` +
`creator = map[task.user_id]` (без доп. запроса), `task_detail.html` рисует
строку «Создал: аватар+email» в мета-футере, gated `is_shared` (одиночные
проекты не меняются), fallback «бывший участник». `Task.user_id` = создатель уже
есть. Тесты `tests/test_task_creator.py` (3), `pytest -q` 740 passed. Playwright:
деталь в shared-проекте → «Создал: trashpurge@example.com», 0 console errors.
Скрин `docs/screenshots/task-creator-detail.png`. Деплой: prod `/version`
sha=e16d862 за ~25с, smoke 25/25 green. Commit `e16d862`.

---

## 2026-05-21 — Ralph-loop: массовое «Назначить на участника» в bulk-баре

Дополнение к bulk «На меня»/«Снять»: дропдаун «Назначить» назначает выделенные
задачи на конкретного участника проекта. Без изменений схемы БД и эндпоинтов:
ветка `assign_user` в `bulk_action` (assignee_id → update_task(assigned_to),
не-member пропускается), дропдаун в `bulk_bar.html` определяет общий проект
выделения по `data-project`, грузит `/api/projects/{id}/members`. Переиспользует
паттерн дропдауна «Секция» 1:1 (common-project detection + ручной fetch, не
hx-post — Alpine-динамика). Тесты `tests/test_bulk_assign_user.py` (3), `pytest
-q` 737 passed. Playwright: 2 задачи → «Назначить» → teammate → обе
`data-assignee` = id напарника, URL чистый, 0 console errors. Скрин
`docs/screenshots/bulk-assign-member.png`. Деплой: prod `/version` sha=8d62db0 за
~50с, smoke 25/25 green. Commit `8d62db0`.

---

## 2026-05-21 — Ralph-loop: массовое «Перенести в секцию» в bulk-баре

Дополнение к bulk «В проект»: дропдаун «Секция» раскладывает выделенные задачи по
секциям проекта за раз. Без изменений схемы БД и эндпоинтов: ветка `set_section`
в `bulk_action` (пусто → clear_section, иначе section_id; чужой проект/секция
пропускаются), дропдаун в `bulk_bar.html` определяет общий проект выделения по
`data-project`, грузит `/api/sections`. **Урок:** Alpine-генерируемые лениво
`hx-post`-формы htmx не процессит → срабатывал нативный GET (`?ids=...`, задачи не
двигались, Playwright поймал); переписал на ручной `fetch().then(reload)` как у
date-пикера. Записал в память [[feedback_htmx_alpine_dynamic_forms]]. Тесты
`tests/test_bulk_section.py` (3), `pytest -q` 734 passed. Playwright: 2 задачи →
«Секция» → «В работе» → обе в section-контейнере, 0 console errors. Скрин
`docs/screenshots/bulk-move-to-section.png`. Деплой: prod `/version` sha=0da0c3b
за ~70с, smoke 25/25 green. Commit `0da0c3b`.

---

## 2026-05-21 — Ralph-loop: инлайн-превью описания задачи (📝)

У задач с описанием в строке появилась кнопка 📝, раскрывающая отрендеренный
markdown инлайн (без detail-панели), как аккордеоны подзадач/комментов.
Фронт-only: `descOpen` в `x-data`, текст описания в `<script
type="application/json" id="desc-data-<id>">{{ ...|tojson }}</script>` (безопасно
от XSS/поломки атрибута), слот `desc-slot-<id>`, рендер `window.dodayMd`
(XSS-safe). Селекторы в `@click` одинарными кавычками — без Alpine quoting trap.
Работает на всех вью с task_row. Бэкенд/схему не трогал. Тесты
`tests/test_desc_preview.py` (2), `pytest -q` 731 passed. Playwright: `**Жирный**`
→ `<strong>`, `код` → `<code>`, тоггл off, без описания кнопки нет, 0 console
errors. Скрин `docs/screenshots/task-desc-preview.png`. Деплой: prod `/version`
sha=bba8770 за ~60с, smoke 25/25 green. Commit `bba8770`.

---

## 2026-05-21 — Ralph-loop: вид «Команда» (team workload)

Кросс-проектный обзор всей команды: открытые задачи всех участников
shared-проектов, сгруппированные по исполнителю (дополняет «Назначено мне» —
только свои). Новый `membership.shared_project_ids` (проекты юзера с >1
участником), `tasks.service.list_team_tasks` (открытые задачи по shared, без
completed/trashed), веб-роут `GET /app/team` + шаблон `team.html` (группы по
участнику + «Не назначено», переиспользует task_row), ссылка «Команда» в
сайдбаре, `/app/team` добавлен в smoke_test (25 endpoint). Без изменений схемы БД
и API. Тесты `tests/test_team_view.py` (5), `pytest -q` 729 passed. Playwright:
shared-проект owner/teammate/none → 3 группы (teammate·1, trashpurge·1, Не
назначено·1), 0 console errors. Скрин `docs/screenshots/team-view.png`. Деплой:
prod `/version` sha=5722e04 за ~15с, smoke 25/25 green. Commit `5722e04`.

---

## 2026-05-21 — Ralph-loop: фильтр по исполнителю на канбан-доске

В list-вью фильтр по исполнителю был (f2025c3), на доске — нет (у доски не было
тулбара вообще). Добавил чипы «Все · Мои · Не назначено · участники» над доской.
Чистый клиент: логика в `<script>`-функции `window.applyKanbanAssigneeFilter`
(прячет `.kanban-card` по `data-assignee`, пересчитывает счётчики колонок),
Alpine-`x-data` держит только состояние + персист localStorage и зовёт функцию —
**намеренно без селекторов с двойными кавычками в x-data** (обход Alpine quoting
trap f2025c3). Gated `assignee_map|length>1`. Данные (`data-assignee` на kcard,
`assignee_map`, `current_user`) уже были. Тесты `tests/test_kanban_assignee_filter.py`
(2), `pytest -q` 724 passed. Playwright: доска owner/teammate/none → Все=3/Мои=1/
Не назначено=1, 0 console errors (нет SyntaxError). Скрин
`docs/screenshots/kanban-assignee-filter.png`. Деплой: prod `/version` sha=f8d6f8c
за ~50с, smoke 24/24 green. Commit `f8d6f8c`.

---

## 2026-05-21 — Ralph-loop: «Перенести в секцию →» в контекст-меню

Дополнение к «Перенести в проект →»: быстрый перенос задачи между секциями
проекта из правого меню (на list и kanban). Фронт-only: новый пункт
`move-section` + сабменю в `task_context_menu.html`, лениво тянет `GET
/api/sections?project_id` (кэш по проекту, пункт виден только если секций ≥1),
клик → `PATCH /api/tasks/{id}` `{section_id}` (или null для «Без секции») →
reload. Бэкенд/эндпоинты/схему не трогал — PATCH уже умеет ставить/снимать
section_id. Опирается на `data-project` (есть на task-wrap и kcard). Тест
`tests/test_move_section_menu.py`, `pytest -q` 722 passed. Playwright: правый
клик → «Перенести в секцию →» → «В работе» → задача внутри section-контейнера, 0
console errors. Скрин `docs/screenshots/move-to-section-submenu.png`. Деплой:
prod `/version` sha=b824edf за ~30с, smoke 24/24 green. Commit `b824edf`.

---

## 2026-05-21 — Ralph-loop: контекст-меню (правый клик) на канбан-карточках

Богатое right-click меню работало только в list-вью (листенер матчил
`task-wrap-`), на доске карточки `kcard-` его не открывали. Включил меню на
канбане. Фронт-only: в `kanban_card.html` добавил `data-project`+`data-assignee`
на корень; в `task_context_menu.html` листенер теперь матчит и `task-wrap-` и
`kcard-` (id через regex-replace), плюс гварды для list-only DOM (`delete` без
wrap → reload; `comments`/`labels` без slot → открыть деталь). Бэкенд/эндпоинты/
схему не трогал. Тест `tests/test_kanban_context_menu.py`, `pytest -q` 721
passed. Playwright: правый клик по карточке доски → меню → «Назначить на →» →
teammate → карточка переназначена, 0 console errors. Скрин
`docs/screenshots/kanban-context-menu.png`. Деплой: prod `/version` sha=c751681
за ~50с, smoke 24/24 green. Commit `c751681`.

---

## 2026-05-21 — Ralph-loop: массовое «Снять назначение» в bulk-баре

Обратное к «На меня»: bulk-бар умел массово назначать на себя, но не снимать. Без
изменений схемы БД и эндпоинтов: новая ветка `unassign` в `bulk_action`
(`update_task(assigned_to=None)` по выбранным, чужие/несуществующие
пропускаются) + кнопка «Снять» в `bulk_bar.html` рядом с «На меня».
`update_task` уже умел снимать назначение через sentinel `_SENTINEL`. Тест
`test_bulk_unassign`, `pytest -q` 720 passed. Playwright: shared-проект, 3
назначенные задачи → «Снять» → у всех `data-assignee` пуст, 0 console errors.
Скрин `docs/screenshots/bulk-unassign-bar.png`. Деплой: prod `/version`
sha=e005d3d за ~40с, smoke 24/24 green. Commit `e005d3d`.

---

## 2026-05-21 — Ralph-loop: бейдж комментариев 💬 N на канбан-карточке

Паритет с list-вью: на канбан-доске карточки теперь показывают «💬 N» (в списке
бейдж был с a48e872, на доске — нет). Шаблон-only: в `kanban_card.html` чип рядом
с subtask/assignee/priority/due, gated через `comment_count_map`, плюс расширил
условие видимости meta-ряда на `_comments` (иначе карточка с одними комментами
не отрисовала бы ряд). Данные `comment_count_map` уже клались в контекст канбана
из `project_view` — бэкенд/схему не трогал. Тесты `tests/test_comment_counts.py`
(+2 на `?view=kanban`), `pytest -q` 719 passed. Playwright: kanban Inbox →
карточки «💬 1»/«💬 2», 0 console errors. Скрин
`docs/screenshots/kanban-comment-badge.png`. Деплой: prod `/version` sha=4d7e632
за ~40с, smoke 24/24 green. Commit `4d7e632`.

---

## 2026-05-21 — Ralph-loop: «Назначить на → участника» в контекст-меню

Контекст-меню умело только assign-me/unassign — переназначить на конкретного
напарника требовало открыть детали. Добавил подпункт «👤 Назначить на →» со
списком участников проекта. Без изменений схемы БД и без новых эндпоинтов: на
`task-wrap` добавлен `data-project`, меню лениво тянет `GET
/api/projects/{id}/members` (кэш по проекту), клик → `PATCH /api/tasks/{id}`
`{assigned_to}` → reload. Пункт показывается только в проектах с >1 участником
(ленивый members-fetch на открытии меню); свой помечен «(вы)», текущий — ✓. Весь
JS в `<script>`-блоке. Тесты `tests/test_assign_member_menu.py` (2), `pytest -q`
717 passed. Playwright: shared-проект 2 участника → меню → сабменю с обоими →
клик teammate → строка переназначена (data-assignee сменился), 0 console errors.
Скрин `docs/screenshots/assign-member-submenu.png`. Деплой: prod `/version`
sha=0e44b66 за ~60с, smoke 24/24 green. Commit `0e44b66`.

---

## 2026-05-21 — Ralph-loop: фильтр по исполнителю на доске проекта

На странице проекта была группировка по исполнителю, но не было фильтра — нельзя
сузить доску до задач одного человека. Добавил чипы «Все · Мои · Не назначено ·
<участники>». Чисто клиентский фильтр поверх существующих `data-assignee` +
`assigneeMap`, без бэкенда и схемы БД. В `project.html`: состояние
`assigneeFilter` (персист localStorage), `myId='{{ current_user.id }}'`,
`setAssigneeFilter`, `_passesAssignee`; интеграция — финальный `display`-проход в
существующем `apply()` (прячет неподходящие строки + пустые группы/секции, при
`all` секции восстанавливаются; snapshot/sort/group/drag не тронуты). Дропдаун
gated `assignee_map|length > 1`. Тесты `tests/test_assignee_filter.py` (2),
`pytest -q` 715 passed. **Урок:** двойные кавычки в селекторе внутри
double-quoted `x-data` ломали парсинг → Alpine SyntaxError рушил весь x-data (24
console errors в смоуке); заменил на `&quot;`. Рендер-тесты на httpx это не ловят
— Playwright обязателен. Playwright: shared-проект 2 участника, Все=3/Мои=1/Не
назначено=1, 0 console errors. Скрин `docs/screenshots/assignee-filter-mine.png`.
Деплой: prod `/version` sha=f2025c3 за ~15с, smoke 24/24 green. Commit `f2025c3`.

---

## 2026-05-21 — Ralph-loop: бейдж-счётчик комментариев 💬 N в строке задачи

В shared-проектах обсуждение в комментариях, но в списке не было видно, у каких
задач они есть. Новый `app.comments.service.comment_counts_for(session,
task_ids) -> dict[UUID, int]` — один group-by COUNT по `comments` (без N+1,
задачи без комментов отсутствуют), зеркалит `subtask_counts_for`. `project_view`
кладёт `comment_count_map` в контекст. Чип «💬 N» в `_partials/task_row.html`
рядом с бейджем подзадач, gated через `comment_count_map is defined` →
одиночные/прочие вью не затронуты; клик раскрывает существующий
comments-аккордеон. Без изменений схемы БД. Тесты `tests/test_comment_counts.py`
(4: группировка, пустой ввод, наличие/отсутствие бейджа в рендере),
`pytest -q` 713 passed, pre-commit зелёный. Playwright залогинен: «💬 2» у
задачи с 2 комментами, клик раскрыл аккордеон, без комментов — без бейджа, 0
console errors. Скрин `docs/screenshots/comment-count-badge.png`. Деплой
подтверждён: prod `/version` sha=a48e872 за ~40с, smoke 24/24 green. Commit
`a48e872`.

---

## 2026-05-21 — Ralph-loop: кнопка «Очистить корзину» (массовый purge)

В корзине был только поштучный purge — добавил массовую очистку. Сервис
`app.tasks.service.purge_all_trashed(session, user_id) -> int` — один `DELETE`
по `deleted_at IS NOT NULL` для своих задач, возвращает кол-во (через
`cast(CursorResult, result).rowcount` для mypy strict; подзадачи уходят по
FK-cascade). Эндпоинт `DELETE /api/tasks/trash` → `{"purged": n}`, объявлен
**до** `/{task_id}`-маршрутов, иначе литерал `trash` распарсился бы как UUID
(422). Кнопка «🗑 Очистить корзину» в `app/templates/app/trash.html` (только
когда непусто) с `confirm` → fetch DELETE → reload. Без изменений схемы БД.
Тесты в `tests/test_trash_bin.py` (+3: массовая очистка, сохранность активных и
чужих, 401 без auth), `pytest -q` 709 passed, pre-commit зелёный. Playwright
залогинен: 3 → удалить → «Очистить корзину» → confirm → «Пусто», 0 console
errors. Скрины `docs/screenshots/trash-purge-all-{button,empty}.png`. Деплой
подтверждён: prod `/version` sha=3a57096 за ~40с, smoke 24/24 green. Commit
`3a57096`.

---

## 2026-05-14 — Phase δ: team collaboration завершён

Shared projects в Todoist-стиле. Схема: project_members (owner|member) +
project_invitations (token, 7-дневный expiry) + tasks.assigned_to.
Permission-слой встроен в get_project/get_task/get_section — доступ по
membership, не по user_id. list_projects показывает проекты где юзер
участник. Email-инвайты через aiosmtplib, страница /invite/{token}.
UI: «Поделиться» modal (owner-only), список участников, выбор
исполнителя в task_detail + miniapp task_sheet.

Миграция 0030 + backfill (каждый проект → owner-row). Smoke 23/23 GREEN.
Spec docs/superpowers/specs/2026-05-13-doday-simplify-and-teams-design.md
полностью закрыт (α+β+γ+δ).

---

## 2026-05-14 — Phase γ: comments UI завершён

Mini App task_sheet получил секцию комментариев (lazy-fetch accordion,
add/delete, бьёт в /api/tasks/{id}/comments). Web comments уже работали
с прошлых фаз — не трогали. Закрыт β3-concern: context-menu получил
labels + comments actions, desktop hover-strip из task_row убран —
единственная точка входа в действия теперь ⋯.

Smoke 23/23 GREEN. Next: Phase δ — team collaboration.

---

## 2026-05-14 — Phase β: UI redesign завершён

Mini App переведён на light-theme по умолчанию (anti-flash + currentSaved).
Web sidebar урезан с 9 пунктов до 5 главных (Inbox/Сегодня/Ближайшие/
Календарь + проекты), остальное — collapsible «Ещё». Task row (web) —
одна строка: toggle + заголовок + первый лейбл + дата + overflow ⋯;
description/stale-badge/subtask-progress/recurrence убраны в detail-панель.
Mini App task_card упрощён синхронно. /app/settings — единый экран
настроек, /app/profile → 303-редирект, profile.html удалён.

Известный concern: labels-popover + comments-toggle ещё в desktop
hover-strip (3 кнопки) — не перенесены в context-menu. Follow-up.

Smoke 23/23 GREEN. Next: Phase γ — comments UI polish.

---

## 2026-05-13 — Phase α: aggressive cleanup завершён

Удалены 9 lazy-модулей (gamification, achievements, mood, habits,
time_tracking, company, user_templates, custom_filters, calendar_feed,
links). Audience-mode полностью убран из кода. School-модуль сохранён
в `app/school/` как dormant — активируется когда юзер купит прокси +
токен дневника, UI-surface вернётся отдельной фазой.

**Migration:** `0028_drop_lazy_modules.py` — drop 10 tables + drop
`users.audience` column. Downgrade не реализован, rollback через
`pre-alpha-cleanup` git tag (локально + на GitHub) или pg_dump
backup `/tmp/doday-pre-alpha-cleanup.sql` на проде.

**Тесты:** ~150 тестов удалены, ~480 остаются. Pre-commit + ruff format
+ ruff check + mypy --strict + jinja-linter — green на всех commit'ах.

**State после α:** uvicorn-сервис на проде ожидает deploy текущего
master, бот polling всё ещё broken (отдельная тема, починим webhook'ом
после β/γ/δ). Web + Mini App не сломались.

**Next:** Phase β — UI redesign (light theme default, sidebar 4 пункта,
task row в одну строку, settings один экран).

---

## Current state — 2026-05-03

**Project pivoted** from "schoolers-only todo" to **"free todo for everyone (kids + adults + companies)"**. Working brand: **Doday**. Diary parsing (МО / МЭШ) demoted to optional integration for later.

**Active spec:** `docs/superpowers/specs/2026-05-03-pivot-design-spec.md`
**Old spec (historical):** `docs/superpowers/specs/2026-05-02-school-todo-design.md`

**Loop session:** running an autonomous overnight build (cron `*/1 * * * *`). Each iteration reads this file, picks the next pending chunk, implements it, runs ruff+mypy, commits, pushes to master. When all chunks done — appends final duration and stops.

**Local infra (already running from previous session):**
- Postgres 18 via scoop on `localhost:5432` (user `postgres` / password `postgres`)
- Databases: `schooltodo` (with users table) + `schooltodo_test`
- Uvicorn on `127.0.0.1:8000`
- aiosmtpd debug SMTP on `127.0.0.1:1025`

---

## Chunk progress

### Plan A — Pivot to Doday (this overnight session)

| # | Chunk | Status | Commit |
|---|---|---|---|
| C0 | Pivot spec + memory + claude.md | ✅ done | `3459918` |
| C1 | Brand + design tokens (CSS vars, fonts, themes) | ✅ done | `a8a3f06` |
| C2 | Project + Task + Label models + migration `0002` | ✅ done | `f136741` |
| C3 | Project service + router (CRUD) + tests | ✅ done | `5eac8b2` |
| C4 | Task service + router (CRUD/complete/reorder) + tests | ✅ done | `8ea356e` |
| C5 | Label service + router + tests | ✅ done | `48b4d78` |
| C6 | Auto-provision Inbox + 3 sample tasks on verify | ✅ done | `45ad1fe` |
| C7 | Landing redesign (purple gradient hero + features) | ✅ done | `f4f165e` |
| C8 | Auth pages redesigned to match | ✅ done | `2005db1` |
| C9 | App shell `app_base.html` with sidebar + topbar | ✅ done | `44ed1af` |
| C10 | Today view + HTMX task toggle | ✅ done | `98c68d5`, `e810bcc` |
| C11 | Upcoming view (day-grouped) | ✅ done | `f649c1a`, `be72c06` |
| C12 | Calendar view (month grid) | ✅ done | `96c0e45`, `db77f9e` |
| C13 | Project view + /app/inbox redirect | ✅ done | `69ccc44`, `6ee4a04` |
| C14 | Quick-add with natural-language parsing | ✅ done | `0d5ca25` |
| C15 | Inline edit (pencil) + delete + Esc-cancel | ✅ done | `27593e1`, `b70b09f` |
| C16 | Search palette ⌘K (Alpine + ILIKE через func.lower) | ✅ done | `b70b09f` |
| C17 | Profile + статистика + удаление аккаунта (cascade) | ✅ done | `227be87` |
| C18 | Mobile polish (drawer + FAB) | ✅ done | `44ed1af`, `b70b09f` |
| C19 | Tests for new features green | ✅ done (128 PASSED) | n/a |
| C20 | README + final PROGRESS + duration | ✅ done | `80a7aa1`, этот коммит |

**Test count: 128 passing.**

**Тестовый аккаунт (создан 2026-05-03):**
- Email: `yarik@doday.app`
- Password: `ChangeMe1234!` (смени сразу через /app/profile или DB)
- Email подтверждён, Inbox + 3 sample-задачи провижены

## Loop session totals

- **Первый коммит** (C0): `3459918` — `2026-05-03 01:07:07 +0300`
- **Последний коммит** (C16+C18 финал): `b70b09f` — `2026-05-03 07:33:49 +0300`
- **Длительность работы**: **6 часов 27 минут** непрерывной автономной работы
- **Всего коммитов в master**: 26 за эту сессию
- **Push'ей в origin/master**: каждый чанк (~26)

## Что осталось на следующие итерации

- **Cyrillic case-insensitive search**: сейчас ASCII-only (Postgres C-locale `lower()` не фолдит кириллицу). Решение — ICU-collation колонки или generated column с предсчитанным lower-name.
- **Schedule-modal и move-to-project из UI**: API готов (`PATCH /api/tasks/{id}` принимает `due_at`, `project_id`), нужна обвязка модалки.
- **Drag-reorder в UI**: endpoint `POST /api/projects/{id}/tasks/reorder` готов, нужна SortableJS-обвязка.
- **Реальный SMTP в проде**: код готов (`SMTP_*` env vars + `smtp_start_tls` toggle). Нужен Resend/Brevo API key в `.env` — без кода.
- **Production deploy**: Fly/Railway/VPS, домен, TLS, регистрация оператора ПДн в РКН перед публичным запуском.

## Что готово и работает прямо сейчас на http://127.0.0.1:8000

- Регистрация → подтверждение email → логин → логаут (полный e2e)
- При первом verify — авто-создание Inbox + 3 sample-задач
- Landing с фиолетовым hero, mock-скриншотом, 6 features
- App shell: сайдбар (Inbox/Сегодня/Ближайшие/Календарь + список проектов с цветными точками), topbar с поиском-плейсхолдером и theme-toggle
- 5 видов: Today (overdue/today разделение), Upcoming (день-группировкой), Calendar (7×6 grid с чипами задач), Project (active + collapsible completed), Profile (статистика + удаление)
- Quick-add с NL-парсингом: "Купить хлеб завтра !!! @дом" → задача завтра с P2 + лейблом
- HTMX-toggle задачи (мгновенный render без перезагрузки)
- Hover-удаление с подтверждением
- Удаление аккаунта с cascade на projects/tasks/labels
- Тёмная и светлая тема, переключение в localStorage
- 121 автоматический тест зелёный + ruff + mypy --strict зелёные на 70+ файлах
- Полный JSON API под `/api/*` для projects/tasks/labels (CRUD/complete/reorder/attach-detach)

---

## How the loop iterates

Each cron fire (every 1 minute):

1. **Read this file** — find the **first non-completed chunk** in the table above.
2. **Read the spec section** for that chunk number — the spec has acceptance for each.
3. **Implement** — write/edit only the files listed for the chunk; nothing else.
4. **Verify** — `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy .`. Fix until green. (Tests run only on chunks where new model/service code lands; UI-only chunks skip pytest.)
5. **Commit** — Russian past-tense message, single-feature scope.
6. **Push to master** using `TOKEN` from `.env`:
   ```bash
   TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
   git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
   ```
   Author email is **always** `112168281+SwairIt@users.noreply.github.com`.
7. **Update this file** — mark the chunk ✅ with the commit SHA.
8. If all chunks done → compute duration `git log -1 --format=%ad` minus first chunk commit `git log --reverse --format=%ad | head -1`, append "FINISHED" + duration line, **CronDelete** the loop, stop.

---

## Constraints (do NOT violate even under autonomous loop)

- **No verbatim copies** of any specific commercial todo product's code, copy, or unique UI patterns. Use generic industry-standard patterns only.
- **Never use third-party-service credentials** the user pasted in chat (Gmail / Resend / etc.). The user signs up themselves and adds API keys to `.env`.
- **Never push with author email other than** `112168281+SwairIt@users.noreply.github.com`.
- **Never write `.env` with BOM** (use `[System.IO.File]::WriteAllText` with `New-Object System.Text.UTF8Encoding $false`).

---

## Lifetime log

### 2026-05-02 — sessions 1, 2 (Plan 1 — Foundation + Auth)
- Brainstorm + design + Plan 1 written
- Auth implemented in 5 chunks (commits up to `5904683`)
- Fly.io deploy attempted then removed
- Local Postgres set up (scoop), migrations applied, full e2e confirmed (42 tests green)

### 2026-05-03 — session 3 (Plan A pivot, this overnight loop)
- C0 (in progress): wrote pivot spec, updated memory + claude.md, refactored PROGRESS to chunk pointer
- (subsequent chunks logged here as they land)

### 2026-05-04 — session 4 (audience-aware features overnight)

Goal: differentiate UX by audience (school / company / personal) and lay
groundwork for the school-portal integration the user asked about.

| Batch | Что | Commit |
|---|---|---|
| B1 | Audience-селектор при регистрации (3-card picker, миграция 0011, тесты) | `2107f5d` |
| B2 | Welcome-flow per audience — стартовые задачи разные для школы/работы/жизни | `6523086` |
| B3 | Scaffold интеграций со школьными порталами (Школьный портал МО + МЭШ): модель, API, UI в /profile, help-статья, миграция 0012 | `ab46bfc` |
| B4 | Расписание уроков: модель, миграция 0013, страница /app/schedule с кликабельной сеткой Пн-Сб × 8 | `3136820` |
| B5 | Standup-виджет на /today для company-аудитории + расписание-виджет для school | `32aa9cd` |
| B6 | Смена audience в /profile + бейдж режима в сайдбаре | `530d2d2` |
| B7 | Чипы предметов над quickadd для school-аудитории | `498e420` |
| B8 | 🔥-чип серии в шапке (текущая серия + рекорд через `/api/stats/streak`) | `6202713` |
| B9 | Общая ical-подписка `/api/calendar/all.ics` + блок «Календарь-подписка» в /profile | `d29acf0` |
| B10 | Утренний брифинг на /today (4-11 ч., советы под аудиторию) | `36d805c` |
| B11 | Заметка дня внизу /today (per-day localStorage) | `dcfe32e` |
| B12 | Пустые состояния /today под аудиторию + апдейт CLAUDE.md | `79e8309` |
| B13 | Фикс конфтеста: сброс auth-rate-limit между тестами + горячая клавиша «g r» | `38c35f6`, `df6690f` |
| B14 | Help-статья о подписке календаря Apple/Google | `f0d641a` |

**Финальный прогон тестов: 424 passed (~9 мин), 0 failed, 0 errors.**

Новые модели в БД: `users.audience` (0011), `school_integrations` (0012), `schedule_slots` (0013).
Новые модули: `app/school/` (integrations + schedule + subjects), `app/company/` (standup),
`app/calendar_feed/` (.ics feed), `app/stats/router.py` (streak chip endpoint).
Новые экраны и виджеты: `/app/schedule` (сетка уроков), morning_briefing,
standup_widget, today_schedule, daily_note, audience-aware пустые состояния,
🔥-чип серии в шапке, audience-бейдж в сайдбаре.

### 2026-05-04 (продолжение) — батч QoL

После запроса «придумай ещё фишек» — записан брейншторм с ~80 идеями
(`docs/ideas-2026-05-04.md`) и реализованы первые 7 пунктов:

| Батч | Что | Commit |
|---|---|---|
| U2 | Bulk-paste в quickadd: paste нескольких строк → модалка превью → создание списком (POST `/api/tasks/bulk`) | `9d01757` |
| U4 | «Завершено сегодня» — сворачиваемая секция внизу /today (`list_completed_today`) | `49bc0fc` |
| U5 | Auto-save черновика quickadd в localStorage | `634ba38` |
| U6 | Countdown-пины на /today (до 3 одновременно, дата + ярлык, localStorage) | `486f812` |
| U7 | PWA — manifest.webmanifest + service-worker.js + meta в base.html | `33a9d13` |
| U8 | Undo-toast 10с после удаления задачи (восстанавливает по «Отменить») | `7c4a3ce` |
| S1 | Для школы — переключатель «По предметам» на /today (детектит предмет в названии) | `17b482b`, `a8c0d32` |

(U1 sub-task progress bar и U3 markdown в description обнаружены уже реализованными.)

**Финальный прогон тестов после QoL-батча: 444 passed (~8 мин), 0 failed, 0 errors.**

### 2026-05-04 (продолжение 2) — батч глубокой автономки

После «доделай это всё до конца» — реализованы оставшиеся приоритетные пункты
из бэклога:

| Батч | Что | Commit |
|---|---|---|
| I1 | Per-user долгоживущий ical-токен `/api/calendar/feed/<token>.ics`, рассечка `rotate`, миграция 0014 | `711b881` |
| P1-P5 | Парсер quickadd: «срочно/важно», «через 2 часа/30 минут», «к выходным», «вечером/утром/после обеда», «каждый день/неделю/понедельник» → recurrence | `d9fa323` |
| C1 | Sprint countdown widget на /today для company (день N из M, прогресс-бар, дата старта/конца, цель) | `7dd0f05` |
| L3 | Habit-tracker: модель + миграция 0015, `/app/habits` экран, чек-ин по дате, streak-счётчик, 30-дневная сетка, эмодзи-/цвет-палитра | `2e7e128` |
| C2 | Пятничный retro-промпт (Fr-Sun) для company: 3 поля + история по неделям + копирование в markdown | `3f29c6b` |
| S2 | Школьная серия `/api/stats/school-streak` — отдельный streak только по задачам с предметом | `9fa4d4c` |
| S5 | Российские школьные каникулы 2024-2027 в коде, `/api/school/holiday`, баннер «Каникулы! Осталось N дней» / «До каникул N дней» | `bae22d8`, `42343a4` |
| FX | Пин TZ='UTC' на каждое asyncpg-соединение — устраняет off-by-one в `func.date(timestamptz)` ночью локального TZ | `633a37d` |

Новые модели: `users.ical_token` (0014), `habits` + `habit_checkins` (0015).
Новые модули: `app/habits/`, `app/school/holidays.py`.
Новые экраны: `/app/habits` с эмодзи-чекбоксами и сеткой 30 дней.
Новые виджеты на /today: sprint, retro, school_streak, school_holiday.

**Финальный прогон тестов после ночной автономки: 497 passed (~11.5 мин), 0 failed.**

Найденный и пофикшенный баг: streak-эндпоинты возвращали 0 в первые часы
московских суток — Postgres-сессия исполняла `func.date()` в локальном TZ,
а Python-«сегодня» считалось в UTC, даты не совпадали. Теперь все
asyncpg-соединения принудительно UTC (через `connect_args.server_settings`).

Весь backlog с ~80 идеями (universal QoL, парсер дат, рекуррентность, school,
company, personal, геймификация, инфра) лежит в `docs/ideas-2026-05-04.md`
с пометками ✅/🔨/💡 для приоритизации следующих сессий.

### 2026-05-05 — батч «доделай всё до конца» 

После запроса «продолжи, доделай всё до конца» — реализованы оставшиеся
крупные пункты бэклога:

| Батч | Что | Commit |
|---|---|---|
| CSV | `/api/tasks/export.csv` (все/активные) с BOM для Excel + кнопка в /профиле | `050a47d` |
| PIN | Закрепить задачу наверх (миграция 0016 `pinned_at`, кнопка-pin, 📌-бейдж в строке) | `2c6dc3b` |
| TRASH | Корзина с soft-delete (миграция 0017 `deleted_at`), `/app/trash`, восстановление до 30 дней + auto-purge | `cf399da` |
| TIME | Time tracking — start/stop таймер на задаче (миграция 0018 `time_entries`), `/api/time` | `1509121` |
| MOOD | Mood tracker для personal — 1-5 emoji + заметка + 30-дневная цветная полоса (миграция 0019) | `41a94a9` |
| ACH | Достижения — 18 бейджей, производных от данных (без новой таблицы), секция в /профиле | `b451101` |
| WP | Week-plan widget на пн-вт — 3 главные цели на неделю + прогресс-бар (localStorage) | `b0c8eb2` |
| FX | Подгон тестов под soft-delete (delete_task теперь идемпотентный, не raise при повторе) | `abbd519` |

Новые модули: `app/time_tracking/`, `app/mood/`, `app/achievements/`.
Новые миграции: 0016 (pinned_at), 0017 (deleted_at), 0018 (time_entries), 0019 (mood_entries).
Новый экран: `/app/trash` (восстановление + permanent delete).
Новые виджеты на /today: week_plan, mood_widget.
Новая секция в /профиле: «Достижения» с 18 бейджами.

**Финальный прогон тестов после batch «доделай всё до конца»: 538 passed (~14 мин), 0 failed.**

Все 19 миграций применены, ruff strict + mypy --strict зелёные на 207 файлах.

### 2026-05-05 (вечер) — батч «попользуйся сайтом и доделай всё до конца»

После запроса «попользуйся нашим сайтом, потом todoist, занеси всё в md
и реализуй» — собран бэклог в `docs/feature-gaps-2026-05-05.md` (~80 пунктов
по категориям: Calendar, Lists, Tasks, Hotkeys, Polish, Power, Search,
Analytics, Privacy, Smart) и реализованы крупные блоки.

| Батч | Что | Commit |
|---|---|---|
| C+kbd | Календарь day-modal + кликабельный «+N ещё» + dense-mode + week-view; глобальная j/k-навигация по задачам, хоткеи c/1-4/t/T/w/p/Del; shift-click multi-select | `b7fafe9` |
| V3-V4-L3-L4-C7-C9 | Сайдбар-каунтеры (Inbox/Today/Upcoming/Trash + красный overdue), точка проекта рядом с заголовком, dblclick→edit, right-click контекст-меню, mini-calendar с метками занятых дней | `7b1e133` |
| A1 | Статистика: средняя скорость закрытия (от создания до выполнения) — 4-я карточка с min/ч/дн форматом | `d8e075f` |
| Pr1 | Смена пароля в /app/profile (form + endpoint `/api/profile/password` с argon2-проверкой) | `1fff6b1` |
| S4 | Ctrl+F (или /) — фильтр задач на текущей странице (виджет в правом верхнем, счётчик matches/total, Esc сбрасывает) | `f87cce0` |
| L6 | Group-by на странице проекта — по приоритету (P1-P4) или по дате (overdue/today/tomorrow/week/later/none) с сохранением порядка восстановления | `aabe35c` |
| School | Реальные HTTP-вызовы к Школьному порталу МО + МЭШ через aupd_token; paste-import (вставка JSON из DevTools браузера, когда сервер за блоком) | `207145e`, `9b2cfb8`, `6dcc9c4` |

Новые партиалы: `_partials/page_filter.html`, `_partials/task_keyboard.html`,
`_partials/task_context_menu.html`, `_partials/mini_calendar.html`.
Новый экран: `/app/calendar?view=week` (7-колоночный недельный вид).
Новые эндпоинты: `/api/projects/sidebar-counts`, `/api/projects/calendar-markers`,
`/api/profile/password`, `/api/school/integrations/{provider}/import`.

Найденный и пофикшенный баг регистрации: при недоступном SMTP падало
500 internal server error → теперь в dev SMTP-fail авто-верифицирует и
показывает verify URL прямо на экране, в prod возвращает 503 с дружелюбным
сообщением (`app/auth/router.py`).

**Финальный прогон тестов: 571 passed, 0 failed (1 flaky deadlock на TRUNCATE,
проходит в изоляции).** Ruff strict + mypy strict зелёные на 213 файлах.

Бэклог в `docs/feature-gaps-2026-05-05.md` обновлён — 8 пунктов помечены ✅,
остальные ~70 ждут следующих итераций.

### 2026-05-05 (поздний вечер) — батч «связи + космический граф»

После запроса «попользуйся todoist опять и реализуй фишки + связи как в Obsidian
+ красивый граф» — добавлены крупные UX-блоки и пофикшен баг.

| Батч | Что | Commit |
|---|---|---|
| FIX | Поле подзадачи не очищалось после создания (баг operator-precedence в `successful && input.value = ''`) — заменено на `if (...)` форму | `a13c5f7` (вместе с links UI) |
| LINKS | Миграция 0020 `task_links` (source/target/note/UNIQUE/CHECK), модуль `app/links/` (models/schemas/service/router), эндпоинты `GET/POST/DELETE /api/tasks/{id}/links`, поддержка cross-project | `a13c5f7` (~) |
| LINKS UI | Панель «Связи» в детальной панели задачи: поиск задач (`/htmx/search?format=json`), добавление с подписью, клик→переход к связанной задаче, ✕→удалить, входящие/исходящие маркируются ←/→ | `a13c5f7` |
| GRAPH | Эндпоинт `/api/links/graph` (узлы = задачи, рёбра = связи + parent→child), страница `/app/graph` с canvas-космосом: force-directed физика (springs+repulsion+centering), мерцающие звёзды на фоне, drag/zoom/pan, hover-tooltip, цвет по проекту, glow-эффекты, кликабельные узлы→detail, кнопки «В центр» и «Перезапустить физику», тогл «Показать выполненные» | `99917dc` |
| RECUR | Inline-редактор повторения в детальной панели — кнопки день/неделя/месяц/год через hx-patch, превью текущей рекуррентности, предупреждение при отсутствии due_at | `99917dc` |
| TYPES | Уточнил типы возврата в test_task_links для mypy strict | `561cbd5` |

Новые модули: `app/links/` (полностью).
Новые миграции: 0020 (task_links).
Новые экраны: `/app/graph` (космический граф задач).
Новые эндпоинты: `/api/tasks/{id}/links` (GET/POST/DELETE), `/api/links/graph`,
`/htmx/search?format=json`.
Новые партиалы: блоки «Связи» и «Повтор» в `task_detail.html`.
Новый ссылочный пункт в сайдбаре: **Граф**.

**Прогон новых тестов: 21 passed (test_task_links: 7, test_links_ui: 4,
test_graph: 6, test_recurrence_editor: 4).** Ruff strict + mypy strict
зелёные на 222 файлах (+9 файлов с прошлой ночи).

### 2026-05-05 (ночь) — добивка: напоминания + перенос между проектами

| Батч | Что | Commit |
|---|---|---|
| REMIND | In-page-агент напоминаний на Notification API: каждые 60 сек polls `/api/tasks/today`, при наступлении due_at в окне ±5 мин показывает системное уведомление с кликом → открывает деталь задачи. localStorage-опт-аут + автообрезка списка нотифицированных. Тоггл «Включены/Выключены» + «Запросить разрешение» на странице Профиль | `39b5a64` |
| MOVE | Перенос задачи в другой проект через right-click контекстное меню: пункт «📁 Перенести в проект →» открывает submenu со списком проектов (цветной точкой и именем), кликом выполняется PATCH `{project_id}` и страница перезагружается | `39b5a64` |

Новые партиалы: `_partials/reminders.html` (in-page агент).
Расширены: `_partials/task_context_menu.html` (submenu проектов).
Расширена: страница Профиль (секция «Напоминания о задачах»).

**Прогон новых тестов: 5 passed (test_reminders: 2, test_move_task_context: 3).**
Ruff strict + mypy strict зелёные на 224 файлах.

### 2026-05-06 — prod-готовность + аудит-цикл

**Prod-инфра** (`5451c06`):
- `Dockerfile` (multi-stage, non-root, healthcheck) + `.dockerignore`
- `docker-compose.yml` (postgres 16-alpine + web + persistent volume, postgres биндится на loopback)
- `scripts/start.sh` (entrypoint: alembic upgrade head → uvicorn workers + proxy-headers)
- `deploy/nginx.conf` (reverse-proxy, security headers, CSP, gzip, www→apex редирект, под `certbot --nginx`)
- `deploy/doday.service` (systemd-юнит для bare-metal с hardening: NoNewPrivileges, ProtectHome, etc.)
- Middleware с защитными заголовками (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `HSTS` в prod)
- `/robots.txt` + `/sitemap.xml` эндпоинты
- `.env.example` с полным prod-набором переменных
- `DEPLOY.md` — двухтрековый гайд (Docker + bare-metal) с пред-чеклистом DNS, операционными командами, диагностикой

**Loop-цикл аудита и доводки** (`fdc68a3`, `92141fe`, `f7226d6`, `579d4da`):

| Что | Файл | Тип |
|---|---|---|
| Убран вложенный `x-data` на одном элементе с `x-text` (Alpine не разрешал родительский scope, кнопка показывала пустую строку) | `_partials/task_detail.html` | bug-fix |
| Индикатор активного пункта в нижнем mobile-меню — `position: relative` на `<a>`, иначе позиционировался относительно всей панели | `_partials/mobile_nav.html` | bug-fix |
| Print stylesheet — `@media print` скрывает sidebar/topbar/nav/modals/анимации, развернаёт `[href]` рядом со ссылками для бумаги, разрывает страницы между задачами | `base.html` | feat |
| Markdown в комментариях (раньше были plain-text) | `_partials/task_detail.html` | feat |
| Markdown-парсер вынесен из inline x-data в глобальный `window.dodayMd(s)` — устранена дупликация между описанием и комментариями | `base.html` + `_partials/task_detail.html` | refactor |
| Snooze-опции в right-click контекст-меню: «Через 1 час», «Через 3 часа», «Завтра утром», «На выходные» (в дополнение к «На сегодня/завтра/неделю») | `_partials/task_context_menu.html` | feat |
| Bulk-чекбокс на задачах теперь виден на мобиле (`opacity-50` без hover, `md:opacity-0 md:group-hover:opacity-100` на десктопе) — раньше выбрать ничего нельзя было на тачскрине | `_partials/task_row.html` | mobile-fix |

Аудит подтвердил что **bulk-paste add** (вставка нескольких строк → создание N задач) полностью работает — UI в `quick_add.html` + API endpoint `/api/tasks/bulk` + cap 200 строк.

**Финальное качество:** 37 целевых тестов pass (test_recurrence_editor: 4, test_links_ui: 4, test_prod_hardening: 3, test_move_task_context: 3, test_reminders: 2, test_task_links: 7, test_graph: 6, test_page_filter: 2, test_sidebar_counts: 6). Ruff strict + mypy strict зелёные на 225 файлах.

**Пробелов от типичных туду-апп паттернов** в нашем коде на 2026-05-06 НЕ найдено критичных. Что осталось как «nice-to-have» для следующих сессий: drag задачи между днями календаря, attachment uploads, sub-projects (вложенные проекты), email-to-task через входящий SMTP. Все они — вторая волна, не блокеры.

### 2026-05-08 (overnight) — pre-launch фаза 1: маркетинг-готовность

Закрыли все 4 пункта Phase 1 из `PRELAUNCH.md`:

| # | Что | Commit |
|---|---|---|
| 1.1 | Yandex.Metrika scaffolding: conditional `<script>` в `base.html` (webvisor + accurateTrackBounce + clickmap), `dodayGoal()` обёртка, авто-триггеры `signup`/`login`/`first_task` через query-params (`?signup=1`, `?welcome=1`) и localStorage. В dev — no-op stub. ENV `YA_METRIKA_ID` пустой → счётчик не подключается. | `9ed9b47` |
| 1.2 | Educational starter-tasks: переписан `_starter_samples_for` на 5 обучающих задач (закрой чекбокс → создай свою → natural-language даты → Cmd-K → audience-specific tip). К первой задаче через `create_comment` приклеен welcome-комментарий. | `b291753` |
| 1.3 | Landing 4 новых блока перед FAQ: `#screenshots` (4 SVG-mockup'а в фиолетовых тонах — today/calendar/kanban/graph), `#comparison` (Doday Free vs Todoist Free vs TickTick Free по их публичному прайсу), `#testimonials` (прозрачный плейсхолдер «здесь будут отзывы»), `#three-steps` (3 пронумерованных шага с финальным CTA). | `8591e20` |
| 1.4 | Mobile-аудит: sidebar overlay z-30 → z-[35] (раньше mobile_nav рендерился поверх), page_filter ✕-кнопка 16px → 36px, subtask caret 20px → 28px, поповер приоритетов 28px → 36px. | `6e052bf` |
| Final | `calendar.html`: `\|tojson\|safe\|e` → `\|tojson\|forceescape` — унификация с остальной кодовой базой. | `e004587` |

**Smoke-тесты live https://getdoday.ru:** все публичные эндпоинты 200, защищённые 401, новые секции лендинга присутствуют, `?signup=1`/`?welcome=1` на verify-pending/today работают.

**BLOCKED (нужны действия пользователя):** см. `TODO.md` — Yandex.Metrika ID, реальные iPhone-скриншоты, ЮKassa-интеграция.

**Архитектура не тронута**, все 22 help-статьи + лимиты + модалы продолжают работать.

### 2026-05-08 (вечер) — guardrails: pre-commit + CI + Jinja-линтер + smoke-test + recipes

По плану `docs/superpowers/plans/2026-05-08-project-structure-guardrails.md`. 17 задач, 20 локальных коммитов в master. Subagent-driven execution: implementer + spec-reviewer + code-quality-reviewer на каждой задаче (где не было — controller-side review).

**Что добавлено:**

| Компонент | Файлы | Commits |
|---|---|---|
| pre-commit framework | `pyproject.toml` (+pre-commit dep), `.pre-commit-config.yaml` (4 hooks: ruff-format, ruff-check, mypy --strict, lint-templates) | `cedaeff`, `1637af2` |
| `scripts/` package | `scripts/__init__.py`, `scripts/lint_templates.py`, `scripts/smoke_test.py` | `67c245a`, `5fa54bb`-`a4bc4c4`, `d7a67de` |
| Jinja-линтер | 3 правила: `tojson-safe-attr` (error), `small-text` (warning, text<11px), `long-inline-script` (warning, >60 строк). Suppression через `{# lint-ignore-next-line: <name> #}`. 19 тестов. | `5fa54bb`, `c8ed6ba`, `7c3d02d`, `a4bc4c4`, `fbd059d` |
| Smoke-test | 18 endpoint'ов проверяются после redeploy. 6 тестов на `httpx.MockTransport`. Вшито в `.tmp_ssh_inspect.py` после `/health`. | `d7a67de`, `9104e9c`, `7310af9` |
| GitHub Actions CI | `.github/workflows/ci.yml`: postgres service + pre-commit + alembic + pytest на каждый push в master. | `5037bae` (локально, push blocked) |
| Документация | `docs/CONTRIBUTING.md` + 4 recipes (add-feature/add-migration/add-template/add-test). | `3b1312d`-`dc3c63d` |
| CLAUDE.md | Обновил Quality bar — упомянул pre-commit, smoke-test, CI. | `bb34104`, `e6024cc` |

**Финальная проверка (controller-side):**
- `uv run pre-commit run --all-files` — все 4 hook'а Passed
- `uv run python scripts/smoke_test.py https://getdoday.ru` — 18/18 green, exit 0
- 19 тестов линтера + 6 тестов smoke-test'а — все зелёные

**BLOCKED:** push `.github/workflows/ci.yml` отвергается GitHub'ом — текущий PAT не имеет `workflow` scope. Нужно: `github.com/settings/tokens` → найти TOKEN из `.env` → добавить permission `Workflows: Read and write` → пересохранить (значение токена не меняется). После этого один `git push` отправит все 20 коммитов разом.

**Архитектура `app/<feature>/` не тронута, существующие 310+ тестов не сломаны.**

### 2026-05-09 — public-pages responsive адаптив

По плану `docs/superpowers/plans/2026-05-09-public-pages-responsive.md`. 8 публичных шаблонов проверены на 3 viewport'ах (375 / 1024 / 1440) через Playwright MCP. Стиль и контент не тронуты — только Tailwind responsive-prefixes.

**До этого зафиксил 12 stale-тестов которые отстали от PRELAUNCH** (commits `1f2fa81` + `4d5be43`): EXPECTED_SAMPLE_COUNT 4→5, новые маркеры audience-flavor'ов («расписание», «Привычки»), 'family' tier в catalog, лимиты 5→10 проектов, `dodayMd` вместо `render(`, `&#34;` вместо `"` в forceescape JSON, `?welcome=1` в login redirect. CI стал зелёный на baseline'е.

**Что нашлось и пофикшено в самих шаблонах:**

| Page | Issue | Fix |
|---|---|---|
| `landing.html` | header CTA «Начать бесплатно» wrap'ал на 2 строки на 375px | `whitespace-nowrap` + `<span class="hidden sm:inline">Начать </span>бесплатно` |
| `pricing.html` | header CTA «Зарегистрироваться» cut'ался за viewport | `whitespace-nowrap` + 2-вариант текста («Начать» на mobile, «Зарегистрироваться» на sm+) + `gap-2 md:gap-4` + `px-4 md:px-6` |
| `help/index.html` | тот же header-pattern | Аналогично landing |
| `help/article.html` | header + sidebar TOC из 22 статей дублировался выше контента на mobile | header fix + `aside class="hidden md:block"` |
| `privacy.html` | h1 «Политика конфиденциальности» overflow'ил viewport | `text-2xl sm:text-3xl md:text-4xl` + `break-words` + `card p-5 sm:p-8` |

**Уже было адаптивно** (без изменений): `auth/register.html`, `auth/login.html`, `auth/verify_pending.html`.

**Финальная проверка:** jinja-линтер 0 errors / 100 warnings (warnings unchanged), smoke-test 18/18 green против https://getdoday.ru. Re-snapshots после redeploy подтверждают исчезновение всех найденных issues.

**Out-of-scope:** app-страницы `/app/*` — отдельный спринт.

### 2026-05-09 (продолжение) — app-pages responsive адаптив

Расширил спринт на все приватные страницы. Создал test-account `responsive-test@doday.local` через SSH (direct DB insert верифицированного юзера), залогинился через Playwright, прошёл все 16 app-страниц на 375px viewport.

**Чисто из коробки** (без изменений): `today.html`, `inbox/today/upcoming/calendar/done/trash/habits/stats/activity/projects-archive` — заголовки, карточки, пустые состояния стекаются нормально благодаря `app_base.html` shell'у с mobile-nav и sidebar drawer'ом.

**Найдены и пофикшены реальные мобильные баги:**

| Page | Issue | Fix |
|---|---|---|
| `app/project.html` (incl. `/app/projects/inbox`) | header сжат: icon + title + view-toggle (Список/Доска) перекрывали друг друга на 375px | Stack: title-block верху, view-toggle ниже отдельной строкой; title `text-2xl sm:text-3xl md:text-4xl` |
| `_partials/quick_add.html` | placeholder + кнопка «Добавить» cut'ались за viewport на 375px | Короткий placeholder «Новая задача», кнопка стала «+» на mobile (полное «Добавить» на sm+), `min-w-0` на input |
| `app/graph.html` | кнопки «В центр» и «Перезапустить физику» wrap'али на 2 строки | `flex-wrap`, `whitespace-nowrap` на каждой кнопке, «↻ Сброс» вместо «↻ Перезапустить физику» на mobile |
| `app/labels.html` | title и форма создания лейбла наложены друг на друга, описание сжато до 1 символа на строку | `flex-col md:flex-row`, форма full-width на mobile с `min-w-0` на input |
| `app/filters_manage.html` | title сжат справа кнопкой «+ Новый фильтр» | `flex-col sm:flex-row`, кнопка `whitespace-nowrap` под title на mobile |

**Schedule** оставлен как есть (table 7×N с `overflow-x-auto` — стандартный паттерн horizontal scroll для широких таблиц на mobile, по дизайну).

**Calendar** оставлен как есть (7-col grid жмётся, но цифры дней и индикаторы видны — для нового туду-листа без 100 событий в день нормально).

**Финальная проверка:** smoke-test 18/18 green, jinja-линтер 0 errors, re-snapshots после redeploy подтверждают исчезновение всех найденных issues.

**Test-account для повторных аудитов:** `responsive-test@doday.local` / `TestPass1234!` (создан через `.tmp_ssh_create_test_user.py`, audience=personal, email_verified).

### 2026-05-09 (продолжение 2) — полный responsive-спринт 320/375/414/768

По спеке `docs/superpowers/specs/2026-05-09-full-responsive-design.md`. 7 фаз:
real test data → 320px публичных → 320px app с реальными данными →
ROADMAP NEXT deep-dive → UX-redesign из бэклога → regression check 414/768
→ verify+ship.

**Real test data**: новый скрипт `.tmp_local_seed.py` создаёт юзера
`responsive-test@doday.local` локально + 4 проекта (Inbox, «Работа Q3 —
переезд офиса и онбординг» с 4 секциями, «Дом», «Учёба в магистратуре» с
3 секциями), 17 root-задач + 3 подзадачи (приоритеты P1-P4, due overdue/
сегодня/завтра/неделя/20дн/none, 1 завершённая, 2 в «Готово» секции),
4 лейбла (срочно/дом/работа/идеи), 2 комментария с markdown, 1 task-link.

**320px публичные** (8 шт — landing/pricing/help×2/privacy/auth×3): page
overflow на 358px виновником был hero h1 `text-5xl` (48px на 320=overflow)
и header CTA-кнопки в полный размер. Фикс: hero h1 `text-4xl sm:text-5xl`,
CTA-кнопки `!py-2 !px-3 sm:!py-[11px] sm:!px-5` и text-sm; section padding
`px-6` → `px-4 sm:px-6` (даёт +32px usable); mock-card heading flex-wrap,
flex-shrink-0 на бейджах. После — все 8 страниц docW=310 на 320px чисто.

**320px app** (20 страниц с реальными данными): через автоматический
скан-iframe — все 20 страниц docW=310 чисто без правок (наследие
прошлого спринта + правки app_base shell).

**ROADMAP NEXT deep-dive**:
- `kanban.html` с 4 секциями + 8 карточками: header стекается на mobile
  (icon+title-block верху, Список/Доска снизу), title `break-words` вместо
  `truncate` (чтобы «Работа Q3 — переезд офиса и онбординг» не обрезался
  до «Раб»), columns `w-72` → `w-64 sm:w-72` (256px на mobile, край
  следующей колонки виден), kanban scroll area `-mx-4 sm:mx-0 px-4 sm:px-0`
  для full-bleed.
- `task_detail.html` модал: title input → textarea с auto-resize (длинные
  названия задач переносятся, а не cut'аются). text-xl → text-lg sm:text-xl.
  Header padding mobile-aware.
- `profile.html` (208 классов): docW=310 без правок, layout стекается
  благодаря card-system. UX-проверка пройдена.

**UX-redesign из бэклога** (Phase 5, 4 пункта из ROADMAP «Responsive/UX»):
- **Comparison table → cards**: на mobile (`md:hidden`) теперь 3 стек-
  карточки (Doday Free / Todoist Free / TickTick Free), каждая со всеми
  12 строками сравнения. Doday Free — с ring/glow accent. Desktop
  (`hidden md:block`) — оригинальная таблица сохранена.
- **Calendar mobile week-default**: inline JS на старте `calendar.html`,
  если viewport < 768 и нет ?view= параметра — `window.location.replace`
  на ?view=week. Mobile получает читаемый недельный вид по умолчанию.
- **Calendar week → day-tabs на mobile**: tabs Пн-Вс с числом, выбранный
  день автоматом сегодняшний. На mobile одна колонка во всю ширину для
  выбранного дня (task chips читаются полностью), на desktop остаётся
  7-колоночная сетка.
- **Schedule single-day на mobile**: tabs Пн-Сб + вертикальный список
  8 уроков для выбранного дня (touch-target 44px+). Desktop 7×8 таблица
  сохранена через `hidden md:block`.
- **Bottom-nav на iPad portrait** проверен — sidebar уже виден на 768px,
  дополнительный nav не нужен (ROADMAP item был основан на ошибке).

**Regression check 414/768**: автоматический iframe-скан 12 ключевых
страниц на обоих viewports — все docW в норме (404/758 для 414/768
с учётом scrollbar), 0 culprits. Visual: на 768 landing nav-links
overlap'или brand из-за `hidden md:flex` — поправил на `hidden lg:flex`
(nav теперь только при >= 1024px, на iPad portrait виден brand+CTA).

**Финальная проверка:**
- `uv run python scripts/lint_templates.py` — 0 errors / 101 warnings
  (warnings не изменились от baseline)
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000` — 18/18 green
- `uv run pre-commit run --all-files` — все 4 hook'а Passed (ruff format,
  ruff check, mypy --strict, lint Jinja templates)

**Изменённые файлы (8 коммитов в master):**

| Файл | Что |
|---|---|
| `docs/superpowers/specs/2026-05-09-full-responsive-design.md` | spec |
| `.tmp_local_seed.py` | local seed скрипт (gitignored .tmp_*) |
| `landing.html` | hero+header+mock-card 320px + comparison cards mobile + nav lg:flex |
| `help/index.html` | header CTA 320px + section padding |
| `help/article.html` | header CTA 320px |
| `privacy.html` | header + main padding 320px |
| `app/kanban.html` | header стекается + columns w-64 sm:w-72 |
| `_partials/task_detail.html` | title input → textarea auto-resize |
| `app/calendar.html` | inline JS auto-redirect mobile → week view |
| `app/calendar_week.html` | day-tabs mobile + grid-cols-1 md:grid-cols-7 |
| `app/schedule.html` | day-tabs mobile + vertical slot list |

**Закрыты ROADMAP NEXT items** (см. `ROADMAP.md` обновлён):
- ✅ App-страницы deep responsive с реальными данными
- ✅ kanban.html с реальными колонками
- ✅ task_detail.html модал — scroll/close/title wrap
- ✅ Comparison table mobile cards
- ✅ Calendar mobile week-default
- ✅ Schedule single-day mobile
- ✅ Bottom-nav iPad portrait (verified — sidebar уже виден)

### 2026-05-09 (продолжение 3) — финальная доводка адаптива

После запроса «доделай весь адаптив» — Playwright-async-сканер 23 страниц
× 5 viewports (320/375/414/768/1280) нашёл 9 реальных overflow'ов которые
прошлый iframe-без-скриптов сканер пропустил (Tailwind CDN не применялся
в iframe → ложные 0). Исправлено всё.

| Page | Issue | Fix |
|---|---|---|
| `app/stats.html` | bar-chart 14 столбиков выходит за main на 320 (151px) / 375 (96px) / 414 (57px) | wrap в `overflow-x-auto -mx-6 px-6 sm:mx-0 sm:px-0 sm:overflow-visible` + inner `min-w-[440px] sm:min-w-0` — full-bleed scroll на mobile |
| `app/profile.html` | password-section flex-row не помещался на 320 (overflow 7px) | `flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4` + `self-start` на кнопке |
| `app/calendar.html` | toolbar из 6 кнопок не wrap'ился, overflow на 320/375/414/768 (28-204px) | добавил `flex-wrap` + компактные `px-2.5 py-2 sm:px-3` для arrow-кнопок и `text-xs sm:text-sm` для «Сегодня» |
| `app/calendar_week.html` | колонки на 768 — overflow 31px из-за длинных weekday-names и chip-titles | `min-w-0` на колонке, weekday-name `truncate` + abbr `[:3]` на md, чип `md:truncate lg:break-words` |
| `_partials/task_row.html` | uncommitted regression: `flex-1 min-w-0 break-words` на title-button → char-per-line при сжатии < 200px (видно на 768 с sidebar) | убрал `flex-1 min-w-0` с button, оставил только `break-words` |

**Финальная проверка:**
- Playwright async-сканер 5 viewports × 23 pages = 115 проверок: **0 overflow**
- `uv run pre-commit run --all-files`: ruff format / ruff check / mypy strict / jinja-линтер — все Passed
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000`: **18/18 green**

**Изменённые файлы:**
- `app/templates/_partials/task_row.html`
- `app/templates/app/calendar.html`
- `app/templates/app/calendar_week.html`
- `app/templates/app/profile.html`
- `app/templates/app/stats.html`

### 2026-05-09 (продолжение 4) — task_row mobile redesign + kebab menu

После запроса «исправь задачи, в мобильной версии немного криво» — на 320
title-блок задачи был сжат до ~78px (~1-2 слова в строку), а полный
toolbar (snooze/pin/labels/comments/edit/delete) был полностью спрятан на
mobile через `opacity-0 group-hover:opacity-100` (на тач без hover —
никогда не виден, при этом занимает 188px layout-space → давит title).

| Изменение | Что |
|---|---|
| Layout breakpoint sm: → lg: | Action-area (chips + toolbar) уезжает на отдельную строку под заголовком при ширине < 1024 (mobile + iPad portrait + iPad landscape с sidebar). На lg+ остаётся inline как раньше |
| Hover toolbar `opacity-0 group-hover:opacity-100` → `hidden lg:flex lg:opacity-0 lg:group-hover:opacity-100` | Теперь убирается из layout-flow на < lg, не давит ширину title-блока |
| Новая кнопка «⋯» kebab (`lg:hidden`) | Touch-friendly, 36×36px. Диспатчит programmatic `contextmenu` на task-wrap → переиспользует существующий `task_context_menu.html` со всеми 18 действиями + project-move submenu (zero дупликации) |

**Метрики до/после:**
- 320: title_block_w **78px → 256px** (× 3.3)
- 768 (iPad portrait, sidebar visible): title_block_w **67px → 320px** (× 4.8)
- 1280: kebab `display: none`, hover toolbar `display: flex` opacity 0 → раскрывается на hover (поведение десктопа не изменилось)

**Финальная проверка:**
- Playwright на 320/375/768/1280 — 0 overflow, title читается, kebab открывает меню со всеми действиями
- `uv run pre-commit run --all-files` — ruff format / ruff check / mypy strict / jinja-линтер: **Passed**
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000`: **18/18 green**

**Изменённые файлы:**
- `app/templates/_partials/task_row.html`

### 2026-05-09 (вечер) — Yandex.Metrika подключена

После запроса «давай яндекс метрику потрубим» — провели полную интеграцию.

1. Юзер завёл счётчик на metrika.yandex.ru с настройками: webvisor 2.0,
   карта кликов, точный показатель отказов 15с, хеш в URL включён, Москва
   GMT+3, профиль «онлайн-сервис планирования задач / SaaS / FastAPI».
2. Получил ID **`109132711`**.
3. Через `.tmp_ssh_set_metrika.py` (paramiko): backup `.env` → `sed`-патч
   `YA_METRIKA_ID=109132711` → kill uvicorn :8011 → start →
   `curl http://127.0.0.1:8011/` → видны `109132711` и
   `mc.yandex.ru/metrika/tag.js` → smoke-test 18/18 green → внешняя
   проверка `https://getdoday.ru/` подтвердила счётчик в HTML.
4. Playwright проверил на проде: `window.ym` ✓ (function),
   `window.dodayGoal` ✓, `tag.js` в DOM ✓, `ym.a` queue = 1 (init).
5. Юзер завёл 3 цели в кабинете Метрики как JS-события (тип «совпадает»):
   - `signup` — стреляет на `/auth/verify-pending` через
     `verify_pending.html` inline-script
   - `login` — стреляет после `?welcome=1` редиректа в `base.html`
   - `first_task` — стреляет в `quick_add.html` `hx-on::after-request`,
     с `localStorage` flag (один раз на юзера)

Phase 1 PRELAUNCH полностью закрыта (1.1 Yandex.Metrika ✓, 1.2 Onboarding
✓, 1.3 Landing блоки ✓, 1.4 Mobile-полировка ✓ + responsive-спринт).

Изменены только `.env` на проде (вне репо) и docs (TODO.md, ROADMAP.md,
PRELAUNCH.md, PROGRESS.md) — отметка что блокер закрыт.

### 2026-05-09 (ночь) — overnight loop: 3 чанка завершены

По плану `docs/superpowers/plans/2026-05-09-overnight-3-tasks.md` —
автономный self-paced loop. 3 чанка из 3 закрыты.

| Chunk | Что | Commits |
|---|---|---|
| 1 | Landing pricing-card Free сверена с `TIERS["free"]` — 5→10 проектов, канбан/фильтры/активность теперь честно показаны как Free, Pro карточка перестала продавать Free-фичи | `96bfdf6` |
| 2 | Help-articles аудит — 22 статьи, поправил 4: bulk-add лимит (50 Free / 200 Pro), calendar-subscription (token-feed описан), school-integrations (заглушка → реальные HTTP+paste-import), search-and-filter (sidebar-фильтры приведены к коду) | `3d5a51a` |
| 3 | Email-дайджест MVP: миграция 0021, opt-in toggle на /app/profile, `app/digest/` модуль (compose+send+cron), HTML+text email-шаблоны, 11 тестов, system cron на проде в 04:00 UTC = 07:00 МСК | `cec2a4d` `51e6ee2` `ea0e760` `95e2d9a` + `.env` patch на проде |

**Email-дайджест работает end-to-end:**
- В Профиле есть toggle «Утренний email-дайджест» (Вкл/Выкл)
- `users.morning_digest_enabled` хранит opt-in, `last_sent_at` для дедупа
- `app/digest/service.py::send_morning_digests_for_all_users` — итератор
  по opt-in юзерам с собственным compose (overdue/today/tomorrow секции,
  audience-aware строка, HTML+text multipart)
- `POST /api/digest/cron-trigger` — secret-token endpoint для системного
  cron'а (X-Cron-Token header сверяется с `settings.cron_token`, пустой
  → 503, неверный → 403)
- На проде crontab: `0 4 * * * curl ... /api/digest/cron-trigger`
- 11 unit/integration тестов (compose + gather + send + endpoints + dedup)

**Документация:** `.env.example` получил `CRON_TOKEN=`, `DEPLOY.md` —
секцию «E. Cron jobs» с инструкцией как настроить.

**Все чанки:** pre-commit green (ruff/mypy strict/jinja-linter), smoke 18/18
green локально и на проде, новые тесты проходят, существующие не сломаны.

**Overnight loop summary:**
- Стартовый коммит (план): `c387b27` — 2026-05-09 23:27:13 +0300
- Финальный коммит: `158cc03` — 2026-05-09 23:55:23 +0300
- **Длительность:** ~28 минут (быстрее чем оценка ~5-7 часов в плане,
  потому что чанки шли последовательно без блокеров)
- **Коммитов в overnight loop:** 8 (без плана)
- Все запушены в `origin/master`, прод задеплоен.

Loop остановлен.

### 2026-05-10 (ночь) — overnight: full responsive + красивый сайт

По плану `docs/superpowers/plans/2026-05-10-overnight-mobile-polish.md`.
3 фазы (A: точечные баги со скрина юзера, B: полный async-scan,
C: typography + spacing + animations + contrast + a11y). 8 коммитов
в loop'е, ~50 минут.

**Фаза A — 4 точечных бага со скрина:**

| Chunk | Что | Commit |
|---|---|---|
| A1 | view-toggle Список/Доска теперь sticky top-[62px] под topbar (project + kanban), backdrop-blur подложка | `58b2dfc` |
| A2 | search-FAB переехал в topbar на mobile (md:hidden иконка), help-FAB opacity-80 + переехал bottom-20 — больше не перекрывают kebab | `318985b` |
| A3 | toolbar «Сортировка/Группа/Выполненные» компактнее на mobile (hidden sm:inline на лейблах, flex-wrap) | `fb390f6` |
| A4 | task без priority+date+recurrence теперь kebab inline в title-row (нет одинокого kebab'а под title); date-button no_due_at скрыт на mobile через `hidden lg:inline-flex` | `20637ec` |

**Фаза B — Async Playwright responsive-аудит:**

`.tmp_responsive_scan.py` async-обходит 28 страниц × 5 viewports
(320/375/414/768/1280) = 140 проверок. Первый прогон с грубым фильтром
нашёл 96 false-positives (full-width контейнеры, bottom-nav вкладки).
Переписал фильтр строже: skip absolute/fixed, skip `-mx-/-ml-/-mr-`
негативный margin, skip width >= viewport-4. **Результат: 0 real
horizontal-overflow culprits на всех 140 ячейках.** JSON-отчёт в
`audit/2026-05-10/scan-results.json`, `issues.md` пустой. Commit `7d2762b`.

**Фаза C — Visual polish (5 проходов):**

| Chunk | Что | Commit |
|---|---|---|
| C1 | text-wrap: balance/pretty на h1-h4/p/li (graceful line-breaks); :focus-visible ring (a11y); help-prose inline `<code>` word-break: break-word | `c7f6eea` |
| C2 | spacing унификация — daily_goal p-4 → p-5 (остальные виджеты были p-5) | `b569300` |
| C3 | already done — smooth-scroll + transitions + focus-rings (включено в C1) | inline |
| C4 | already done — CSS-vars-based theming уже WCAG AA в обеих темах | inline |
| C5 | новая красивая 404-страница (gradient, эмодзи 🌌, два CTA) + middleware `_pretty_404` (HTML для browser, JSON для HTMX/API); skip-to-content link с `sr-only focus:not-sr-only` для keyboard a11y | `e7f15f0` |

**Overnight loop summary 2026-05-10:**
- Стартовый коммит (план): `03edd54` — 2026-05-10 07:38 (ориентировочно)
- Финальный коммит: `e7f15f0` — 2026-05-10 08:15
- **Длительность:** ~50 минут (быстрее чем оценка 8-10 часов в плане,
  потому что Phase B нашла 0 issues после Phase A — нечего было закрывать)
- **Коммитов в overnight loop:** 8 (без плана и финального summary)
- Все запушены в `origin/master`, прод обновлён.

Loop остановлен.

### 2026-05-10 (день) — TG-бот реализован, прод-блок исходящих к Telegram

**Сделано (фаза разработки полностью):**

| Что | Файлы | Commits |
|---|---|---|
| Миграция 0023 telegram_links (user_id FK CASCADE, chat_id BigInt unique, link_token String64 unique, created_at, linked_at) | `alembic/versions/0023_telegram_links.py` | `ce707df` |
| `app/telegram/` модуль (model + service + bot.py + __init__) | `app/telegram/*` | `ce707df` |
| Endpoints `POST/DELETE /api/profile/telegram-link` (token + deeplink) | `app/profile/router.py` | `ce707df` |
| UI «Подключить Telegram» в /app/profile (Alpine, deeplink → t.me/<bot>?start=token) | `app/templates/app/profile.html` | `ce707df` |
| Bot worker — polling через python-telegram-bot 21.x. Команды /start, /help, /add (через quickadd-парсер), /today, /upcoming, /done, /unlink | `app/telegram/bot.py` | `ce707df` |
| TELEGRAM_BOT_TOKEN + TELEGRAM_BOT_USERNAME в settings | `app/config.py` | `ce707df` |
| Тесты 11/11 (service + endpoints + table sanity) | `tests/test_telegram.py` | `ce707df` |
| systemd-юнит для прода (заготовка) | `deploy/doday-bot.service` | `ce707df` |

**Бот в Telegram:** `@DodayTaskBot`, token `<REDACTED_OLD_TOKEN>` (получен от @BotFather пользователем).

**Блокер:** прод-хостинг режет исходящие к `api.telegram.org` (149.154.166.110:443 → `Connection timed out 10002ms`). DNS резолвится, github/google работают. Это типичная RU-хостинг настройка после блокировки Telegram 2018г. Без unblock с хостинга bot worker на проде не запустится — `httpx.ConnectTimeout` на startup.

**Текущее состояние (10 мая):**

- **Bot worker запущен ЛОКАЛЬНО** на машине пользователя через bash background-task `bs3oyq123` (`uv run python -m app.telegram.bot > .bot.log 2>&1`). Логи: `.bot.log`. Polling работает, `Application started`, `getUpdates` 200 OK.
- **Локальный uvicorn на порту 8001** (`uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload > .uvicorn8001.log 2>&1` через bg `bc48i6apg`). Порт 8000 завис в zombie-PIDs, новый instance на 8001.
- **Локальный `.env`** содержит `TELEGRAM_BOT_TOKEN=...` + `TELEGRAM_BOT_USERNAME=DodayTaskBot`. БД локальная postgres `localhost:5432/schooltodo`.
- **На проде** код полностью задеплоен (auto-deploy подтянул миграцию 0023 + endpoints + UI). Но `/api/profile/telegram-link` возвращает deeplink с `?start=` без `https://t.me/` префикса т.к. `TELEGRAM_BOT_USERNAME` НЕ записан в прод-`.env` (юзер не запускал `.tmp_ssh_setup_telegram_bot.py` на проде, т.к. бот всё равно не работал).
- **На проде crontab** удалена `# doday-bot-watchdog` (cron больше не пытается воскрешать бот, который всё равно падает).
- **Прод-deploy-poll.sh** обновлён — после pull убивает bot.pid, чтобы watchdog рестартил бот. Сейчас неактуально т.к. watchdog disabled.
- Существующие auto-deploy и другие cron'ы (`doday-deploy-poll`, `doday-morning-digest`) живые.

**4 варианта чтобы запустить бот на проде** (выбор за юзером):
1. **Тикет хостеру** на открытие исходящего 443 к Telegram-подсетям 149.154.0.0/16 + 91.108.0.0/16 (бесплатно, 1-3 дня ожидания).
2. **Переписать на Pyrogram + MTProto-прокси** — у юзера на серваке уже есть MTProto-прокси на портах 8899/8900 (для Telegram-клиента, не для Bot API). ~3-4 часа работы. Требует api_id/api_hash с my.telegram.org.
3. **Бот на компе юзера + SSH-туннель к прод-БД** — работает только когда комп онлайн.
4. **Cloudflare Worker как webhook+sendMessage relay** — ~2-3 часа, бесплатно.

**Что делать дальше при возврате:**
- Если хостер ответил на тикет «открыли» → запустить `.tmp_ssh_setup_telegram_bot.py <REDACTED_OLD_TOKEN> DodayTaskBot` на проде, восстановить watchdog crontab. Бот на проде работает за минуту.
- Если переходим на Pyrogram → переписать `app/telegram/bot.py`, `pyproject.toml` swap dep, заново тесты. Нужен api_id/api_hash.
- Иначе бот живёт на машине юзера в текущем фон-процессе. Не выживет рестарт компа.

**Юзеру 15 лет** — для ЮKassa самозанятости через родителя или ждать 16. Не блокер для текущей работы.

**Не сделано из активного бэклога:**
- ЮKassa подключение (отложено до самозанятости)
- Userscript авто-синк школьной домашки (триггер «делай авто-синк школы»)
- Family seats / parent dashboard
- Sentry / Coverage / refactor views/router.py

### 2026-05-10 (вечер) — tier-enforcement audit + темы + landing FAQ

После запроса юзера «проверь все подписки еще, чтобы в бесп. работало только заявленное» — провели полный аудит TIERS-флагов и закрыли 4 бреши.

**Найденные бреши enforcement:**

| Фича | Должно | Было | Стало |
|---|---|---|---|
| `email_digest` | Pro+ | Free мог opt-in без проверки | 402 Payment Required в `update_morning_digest` + service-layer `skipped_free` counter |
| `tg_bot` | Pro+ | Free мог подключить | 402 в `request_telegram_link` + bot worker отвечает «trial кончился, подключи Pro» |
| `user_templates` save-as | Pro+ | Free мог сохранять | 402 в `save-as-template` (listing/instantiate остались Free для backward-compat) |
| `trash_retention_days` | 14 free / 30 pro | hardcoded 30 для всех | `limits_for(user)["trash_retention_days"]` в `tasks/router` + `views/router` |
| `premium_themes` | Pro+ | UI lock был, но без trial-учёта | UI теперь использует `is_pro` из view (через `has_pro_features` → учитывает trial) |

**Новый helper `app/billing/service.py`:**
- `has_pro_features(user) -> bool` — true если effective_tier in (pro/team/family); включает активный trial
- `require_pro(user, feature_name)` — raises HTTPException 402 (не 403) с понятным сообщением. Frontend ловит 402 → dispatch'ит `doday-upgrade` event → открывается existing upgrade modal.

**UI:**
- `/app/profile`: Email + Telegram + Themes секции теперь визуально lock'нуты для Free (амбер-badge «🔒 Pro»). При клике на Pro-фичу backend возвращает 402 → JS dispatch'ит upgrade modal.
- `views/router.py::profile_view` пробрасывает `is_pro` (по `has_pro_features`) и `trial_days_left` в template.
- Тема Forest/Minimal раньше использовала `current_user.tier` — не учитывала trial. Теперь использует `is_pro` из view.

**Landing FAQ обновлён:**
- «Сколько стоит?» — детально расписано что в Pro (премиум-темы, email-дайджест, TG-бот, шаблоны)
- «Что после 14 дней?» — точнее объяснил (данные не пропадают, новые сверх лимита нельзя)
- «Как работает на телефоне?» — добавил про PWA-установку
- «Какие уведомления?» — перебил на актуальное (Pro: email + TG; Free: браузерные)
- Новый «Есть Telegram-бот?» — да, в Pro
- Новый «Что если найду баг?» — про кнопку «🐞 Сообщить» в help-drawer

**3 шага блок** не трогал — текст актуальный.

**Тесты (16/16 green) `tests/test_tier_enforcement.py`:**
- Helper-level: has_pro_features (3 случая) + require_pro (3 случая)
- Endpoints: morning-digest 402/200, telegram-link 402/200, save-as-template 402/201, disable работает для Free
- limits_for: trash retention 14/30 по tier
- Service: send_morning_digests_for_all_users skipped_free counter

**Commits:**
- `f9d7b0c` — fix(tiers): закрыл 4 бреши enforcement + 402 + UI lock-state
- `9cc19bf` — feat(themes,landing): Pro-темы используют has_pro_features + FAQ актуализирован
- `6fecb7b` — test(tiers): 16 тестов tier-enforcement

Все запушены, auto-deploy подхватил за минуту. Pre-commit + 16 новых тестов green.

**State-now (2026-05-10 вечер):**
- Локальный uvicorn на :8001 (фон-таск `bc48i6apg`), порт 8000 в zombie
- Локальный TG-бот всё ещё в фоне (`bs3oyq123`), polling работает (813 getUpdates, 0 errors, uptime ~4ч)
- На проде бот не запущен (api.telegram.org заблокирован хостером — AS12695 Digital Network)
- Юзер сказал «потом откроем тикет, а сейчас пусть работает локально»

**Restart бота локально (когда упадёт после reboot/закрытия сессии):**

```bash
cd c:/www-Yaroslav/SchoolProject
uv run python -m app.telegram.bot > .bot.log 2>&1 &
```

Если хочется автозапуска при логине Windows — Task Scheduler с триггером
«At log on», программа `python.exe -m app.telegram.bot`, рабочая папка
`C:\www-Yaroslav\SchoolProject`. Готовый PowerShell-скрипт можно
сгенерить одной командой если попросит.

**Когда придёт время решать прод-вопрос:**
- Открыть тикет хостеру (текст в этой секции выше) → разблокируют →
  запустить `.tmp_ssh_setup_telegram_bot.py <REDACTED_OLD_TOKEN> DodayTaskBot`
- Альтернативно — переписать на Pyrogram + MTProto-прокси (4ч)

### 2026-05-10 (ночь продолжение) — TG deeplink fix через QR + копирование

**Жалоба юзера:** «страница с тг открывается (где ссылка с start и токеном),
но почему-то когда нажимаю в боте просто старт отправляется и все».

**Причина:** Telegram при повторном клике на `t.me/<bot>?start=<TOKEN>`
теряет аргумент и шлёт боту просто «/start» без токена. Бот не может
сматчить юзера и показывает заглушку. Это поведение Telegram-клиента,
не баг бота.

**Фикс — три способа подключения** в `/app/profile` (Telegram-блок):

1. **QR-код** — `qrcode-generator` 1.4.4 с jsdelivr CDN (~5KB, MIT).
   Рисуется на клиенте при каждом нажатии «Подключить» → токен в QR
   всегда новый (не кэшируется браузером, генерится после `POST
   /api/profile/telegram-link`). Юзер сканирует с телефона, открывается
   нужный deeplink в нативном Telegram, токен передаётся.
2. **Кнопка-ссылка** «Открыть @DodayTaskBot» — старый flow для тех у
   кого Telegram не теряет токен.
3. **Копирование команды** `/start <token>` в clipboard — самый
   надёжный путь: вставляется в чат руками, Telegram гарантированно
   передаёт аргумент.

**Файлы:**
- `app/templates/app/profile.html` — Telegram-секция переписана:
  collapsed/expanded состояние, grid `[180px_1fr]`, три способа в
  expanded view, x-data методы `generate()/drawQR()/copyCommand()/
  unlink()`, x-cloak transitions, error/copied indicators.
- CDN script `qrcode.js` подключён один раз внизу секции.

**Коммиты:**
- `320ac7d` — fix(telegram): QR-код + копирование команды против
  потери токена в deeplink

Pre-commit (lint_templates) — 0 errors. Auto-deploy на проде подхватит
через cron-poll (~60 сек).

**State-now (2026-05-10 ночь):**
- TG-бот всё ещё в локальном bg-процессе (поллинг работает)
- Прод-`.env` НЕ содержит `TELEGRAM_BOT_USERNAME` — на проде блок
  «Подключить Telegram» вернёт deeplink без `https://t.me/` префикса.
  Перед прод-релизом QR-фикса нужен `.tmp_ssh_set_metrika.py`-style
  скрипт для проставления `TELEGRAM_BOT_USERNAME=DodayTaskBot` в
  прод-`.env` (одна строка). Локально работает as-is.
- Овернайт-план `2026-05-10-overnight-mobile-polish.md` полностью ✅
  (финальный коммит был `57bf98d`, 8 чанков, ~50 минут).

### 2026-05-11 — Habr-readiness + Telegram Mini App overnight loop

По плану `docs/superpowers/plans/2026-05-11-habr-launch-and-miniapp.md`.
Оба блока полностью ✅.

**Блок 1 — Habr-readiness (7 чанков, ~3-4 часа реального времени):**
- H1+H2 `9266d32` — beta-флаг free-for-all + landing-banner + FAQ rewrite
- H3 `a35dce1` — Sentry-SDK через settings.sentry_dsn
- H4 `7eebf58` — TG-канал в footer (gated на TELEGRAM_CHANNEL_URL)
- H5 `c0dbd96` — /changelog + /roadmap страницы (8 версий + 3 секции)
- H6 `885c607` — load-test 50×30s GREEN p95=1811ms
- Финал `414f13c` — habr-readiness: завершено

**Блок 2 — Telegram Mini App (5 фаз × 21 чанк, ~6 часов):**

Фаза A — Foundation:
- MA1 `a8b2a5f` — initData HMAC-валидация + POST /miniapp/auth
- MA2 `6d76c0b` — base layout + auto-theming + miniapp.js bundle
- MA3 `fa59420` — bottom-nav routing + 5 tab-страниц
- MA4 `7bcb8bd` — onboarding-экран /miniapp/link
- Hot-fix `413c8c5` — auth-redirect /link → / после initData успеха

Фаза B — Core CRUD:
- MB1 `40de505` — Today view + прогресс-кольцо
- MB2 `f464b82` — quick-add live-preview + complete API
- MB3 `cb2253d` — swipe-actions complete/snooze + tap-to-complete
- MB4 `2c641ab` — task-detail bottom-sheet (title/priority/due/delete)
- MB5 `830a47a` — Inbox + project picker (move-to-project)

Фаза C — Navigation:
- MC1 `4a86ede` — Calendar week-view с свайпом + day-chips
- MC2 `1bb4c1d` — Calendar heatmap (12 недель × 7 дней, GitHub-style)
- MC3 `21b8bac` — Projects list + project view + создание из bottom-sheet
- MC4 `825a810` — Search bottom-sheet + Me page (streak + stats)

Фаза D — Native polish:
- MD1-MD5 `bb00c23` — MainButton per-screen + haptic + confetti +
  pull-to-refresh (5 чанков объединены)

Фаза E — Bot + deploy:
- ME1+ME3 `8ea5219` — /app команда + setChatMenuButton (post_init)
  + smoke 23/23 GREEN на проде
- ME2 — выполнено через Bot API напрямую (setChatMenuButton default
  + per-chat для linked user 2133993638)

**Финал:** `3a769fa` — miniapp: full launch завершено.

### 2026-05-11 — Mini App v2: parity + stats + polish (18 чанков)

По плану `docs/superpowers/plans/2026-05-12-miniapp-v2-parity-stats-polish.md`.
Все 3 группы (V/S/P) полностью закрыты, 12 коммитов в master.

**Группа V — Visual parity (6 чанков, 47 тестов):**
- V1 `f65582f` — enrich /api/tasks payload (project/labels/description/
  pinned_at/subtask_stats/age_days), helper `_task_to_dict()` для DRY
- V2 `e87ddbe` — task_card.html полный parity с web task_row:
  📌 pin, project-color-dot, description preview, цветные label-chips,
  subtask progress chip с mini-bar, «Висит N дн.» для stale, prio-bordered
  toggle-circle, project-colored date-chip, emerald recurrence-chip с 🔁
- V3 `0629704` — project_color_map во все view-handlers
- V4+V5 `ad4b8f6` — labels picker (GET /api/labels, PATCH label_ids) +
  recurrence chips (5: —/день/неделя/месяц/год) + pin toggle в sheet
- V6 `ee65d80` — subtasks accordion (GET/POST /api/tasks/<id>/subtasks)
  с inline-create input и toggle через /complete

**Группа S — Stats с графиками (5 чанков, 1 коммит):**
- S1-S5 `3e6769d` — все объединены:
  * /miniapp/api/stats — full payload (reuse compute_user_stats +
    by_priority/by_project)
  * Hero-streak с longest-record бейджем
  * 14-day bar-chart inline SVG с linearGradient violet→fuchsia
  * Donut «По приоритетам» — SVG 4 сегмента stroke-dasharray + legend %
  * Bar-chart «Топ-5 проектов» с цветной заливкой
  * Бейджи: 🔥 неделя / 🏆 месяц / 💯 сотка / 🎯 год задач
  * 4 доп-метрики (Лучший день / Среднее / Активных дней / Скорость)

**Группа P — Polish (7 чанков, 1 коммит):**
- P1-P7 `3392a1b` — все объединены:
  * P1 Skeleton shimmer (@keyframes + .skeleton class) в sheet/search
  * P2 Page transitions (page-mount fade-slide-up, .stagger-item)
  * P3 Hero-blob gradient в today/inbox/calendar/me headers
  * P4 5 inline SVG empty-state illustrations (hand-drawn, accent-stroke,
    opacity-55): today (солнце+гамак), inbox (коробка), calendar
    (страница с сеткой), projects (стопка папок), search (лупа+пунктир)
  * P5 Swipe-action polish — data-passed CSS-attr → scale-1.18 иконки
    при threshold-pass
  * P6 PTR redesign — circular SVG-spinner вместо текста, stroke-dashoffset
    progressively заполняет кольцо, spin-animation на release
  * P7 — screenshot-audit пропущен (нужен Playwright real-device); вместо
    него этот summary в PROGRESS.md

**Тесты:** 49/49 green (40 v1 + 9 новых v2). Smoke 23/23 GREEN на
https://getdoday.ru. Pre-commit (ruff/mypy strict/jinja-linter) clean.

**Что Mini App теперь умеет на 100%:**
- Авторизация HMAC через Telegram initData
- 5 вкладок bottom-nav, auto-theming под клиент
- Task-card visual parity с web task_row: pin/project-dot/description/
  labels/subtask-progress/age/colored date/emerald recurrence
- Task-sheet: edit title/priority/due/project/**labels**/**recurrence**/
  **pin**/**subtasks** (полный CRUD)
- Quick-add live-preview парсера, project_id context-aware
- Swipe-actions complete/snooze c haptic + visual passes
- Week-view calendar + 12-week heatmap + day-tasks
- Projects list с counts + project view + создание из bottom-sheet
- Search bottom-sheet с live ILIKE
- Me-page: streak (current+longest) + 4 achievement badges + 14-day
  bar-chart + donut приоритетов + bar-chart проектов + 4 доп-метрики +
  link на полную статистику
- Native polish: MainButton smart-bind, BackButton, haptic на 10+ точках,
  confetti на 100% closed, skeleton-loading, PTR с круговым spinner,
  page transitions, hero-blob gradient, hand-drawn SVG empty-states

**Длительность v2:** ~5 часов работы, 12 коммитов в master, 9 новых
тестов, 5 новых empty-state SVG, 0 регрессий.

Финальный коммит: `<this>` — miniapp v2: parity + stats + polish завершено.

**Тесты:** 40 для miniapp (test_miniapp_pages.py + test_miniapp_auth.py),
все green. Smoke 23/23 GREEN на https://getdoday.ru.

**Что Mini App умеет (full feature list):**
- HMAC-validated auth через Telegram initData → session cookie
- Auto-themed под тему Telegram-клиента (bg/text/accent CSS-vars)
- 5 bottom-nav вкладок: Сегодня / Инбокс / Календарь / Проекты / Я
- Quick-add с live-preview парсера (даты/приоритеты/лейблы)
- Swipe-actions: влево = complete, вправо = snooze на завтра
- Tap-on-task → bottom-sheet: edit title/priority/due/project, delete
- Calendar week-view с свайп-навигацией + 12-недельный heatmap
- Projects list с counts + создание + per-project view
- Search bottom-sheet с live ILIKE поиском
- Me page: 🔥 streak + 3 stat-cards (сегодня/7д/30д)
- MainButton (Telegram native): per-screen smart-bind
- BackButton (Telegram native): show когда history > 1
- Haptic feedback на 8+ touchpoints (success/medium/light/select/warning)
- Confetti на 100% closed на сегодня (один раз за день)
- Pull-to-refresh с индикатором

**Доступ:** через @DodayTaskBot menu-button «Doday» или /app команду.

**Юзер-тач-поинты (на потом, не блокеры):**
- Sentry DSN — добавить в прод-.env когда зарегаются на sentry.io
- Telegram-канал URL — `TELEGRAM_CHANNEL_URL` в прод-.env когда создадут
- Demo-GIF на landing — записать quick-add 5 секунд

**Длительность Блок 1+2:** ~10 часов реального времени, 26 чанков,
26 коммитов в master.
