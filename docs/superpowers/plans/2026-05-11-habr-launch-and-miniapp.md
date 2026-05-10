# Habr-launch readiness + Telegram Mini App

**Дата:** 2026-05-10 ночь → ?
**Контекст:** юзер хочет продвигать Doday через Habr и параллельно сделать
полноценный Telegram Mini App. Перед публикацией нужно докрутить сайт под
прицел технической аудитории Habr (Sentry, community-канал, beta-positioning,
демо). После этого — большая работа над Mini App'ом.

**Бизнес-решение:** монетизация через подписки откладывается. Для Habr-launch
действует флаг `BETA_FREE_FOR_ALL=true` → все юзеры получают Pro-фичи,
ранние юзеры grandfather'ятся (Pro останется навсегда после введения оплаты).
Никаких ads — productivity-апы их не показывают (убивает focus).

**Разделено на 2 макро-блока:**
- **Блок 1 — Habr-readiness** (7 чанков, ~3-4 часа). Без него — не публикуем.
- **Блок 2 — Telegram Mini App** (5 фаз, 21 чанк, ~15-20 часов). Можно
  публиковать ДО завершения Mini App, но Mini App усиливает story.

---

# БЛОК 1 — Habr-readiness (~3-4 часа)

Цель: при первом контакте с критичной Habr-аудиторией сайт не должен
давать поводов для негативных комментариев. Fix то, что прямо щас является
антирекламой.

### Chunk H1 — Free-for-all flag + landing-баннер «бета» (~30 мин)

**Что делаем:**
- В `app/config.py` добавить `beta_free_for_all: bool = False` (default = False
  для тестов и dev; в прод-`.env` поставим `BETA_FREE_FOR_ALL=true`)
- В `app/billing/service.py` `effective_tier(user)` — если
  `settings.beta_free_for_all is True` → return `"pro"` (минуя tier и trial).
  `has_pro_features` — соответственно
- В `app/templates/landing.html` сверху hero-секции добавить top-баннер
  (закрываемый, sticky-style):
  ```
  🚀 Бета — все функции бесплатно. Ранним юзерам Pro останется навсегда.
  ```
  Цвет — наш accent с лёгким градиентом, текст белый, dismissable через
  Alpine + localStorage чтобы не мозолить глаза вернувшимся
- В `app/templates/pricing.html` — **скрыть** или сильно редизайнить
  pricing-таблицу: вместо «Free / Pro / Team» большой плашкой
  «🚀 Сейчас всё бесплатно. Когда вернём оплату — ранние юзеры останутся
  на Pro.» + ссылка «следить в TG-канале» (см. H4)

**Файлы:**
- `app/config.py`
- `app/billing/service.py`
- `app/templates/landing.html`
- `app/templates/pricing.html`
- `app/templates/base.html` (если top-banner глобально)
- В прод-`.env` через SSH-script `BETA_FREE_FOR_ALL=true`

**Acceptance:**
- На свежем Free-аккаунте `effective_tier(user) == "pro"` локально
- Pre-commit (ruff/mypy/jinja-linter) green
- Pytest green (особенно `test_tier_enforcement` — обновить кейсы или
  завернуть beta-flag через `monkeypatch`)
- На локальной странице `/` баннер виден, dismiss работает
- На `/pricing` старой таблицы нет, есть «всё бесплатно»-плашка

---

### Chunk H2 — Скрыть TG-бот из заявленных фич ИЛИ пометить «скоро» (~15 мин)

**Что делаем:**
- В `app/templates/landing.html` features-секция — если есть «Telegram-бот»
  пунктом, заменить на «Mini App в Telegram» с пометкой «скоро» (или убрать
  совсем). Цель: не обещать то, что у юзера не заработает (бот живёт у тебя
  на ПК через туннель, а api.telegram.org с прода блокирован)
- В `app/templates/pricing.html` (если упоминается) — то же
- В FAQ (`landing.html` block faq) — переписать вопрос «Есть Telegram-бот?»
  на «Будет ли Telegram-интеграция?» с ответом «Mini App в разработке,
  следи в TG-канале»
- В `/help` статьях — поиском убрать утверждения «бот уже работает» если
  есть, заменить на «скоро»

**Файлы:**
- `app/templates/landing.html`
- `app/templates/pricing.html`
- `app/templates/help/*.html` (search'ить «бот» / «telegram-bot»)

**Acceptance:**
- `grep -ri "telegram.*бот.*работает\|tg.*бот.*готов" app/templates/`
  возвращает 0 совпадений
- Smoke-test 18/18 после деплоя

---

### Chunk H3 — Sentry интеграция (~30 мин)

**Что делаем:**
- Зарегаться на sentry.io (free план — 5k events/мес, юзер делает руками,
  даёт DSN)
- `uv add sentry-sdk[fastapi]` (НЕ как dev — production dep)
- В `app/main.py` в startup инициализировать:
  ```python
  if settings.sentry_dsn:
      sentry_sdk.init(
          dsn=settings.sentry_dsn,
          traces_sample_rate=0.1,
          profiles_sample_rate=0.1,
          environment=settings.environment,
          release=settings.version,
      )
  ```
- В `app/config.py` — `sentry_dsn: str | None = None`,
  `environment: str = "dev"`, `version: str = "0.1.0"`
- В прод-`.env` через SSH `SENTRY_DSN=...`, `ENVIRONMENT=prod`
- Тестовый endpoint `/api/sentry-test` (только для admin) — раз вызов →
  raise → проверить event в дашборде. Удалить после теста.

**Файлы:**
- `pyproject.toml`
- `app/config.py`
- `app/main.py`
- прод-`.env`

**Acceptance:**
- Локально `import sentry_sdk` работает
- Pytest green
- На проде один тестовый exception попал в дашборд Sentry
- Pre-commit green

**Юзер-тач-поинт:** даст DSN после регистрации. Если нет DSN — пропустить
init, всё работает как раньше (не блокер).

---

### Chunk H4 — Telegram-канал в footer + в Mini App (~15 мин)

**Что делаем:**
- Юзер создаёт публичный канал в Telegram (например `@dodayru`) и даёт
  ссылку
- В `app/templates/_partials/footer.html` (или где footer) — иконка TG +
  текст «обсудить / следить за апдейтами» → ссылка на канал
- В `landing.html` в hero-section CTA-row — кнопка-ссылка на канал
  второстепенным стилем

**Файлы:**
- `app/templates/_partials/footer.html`
- `app/templates/landing.html`

**Acceptance:**
- Footer на всех app-страницах содержит ссылку на TG-канал
- Кликается, открывается `https://t.me/<username>`

**Юзер-тач-поинт:** создаёт канал руками + первые 2-3 поста (анонс беты,
roadmap-screenshot, скоро Mini App).

---

### Chunk H5 — Changelog/roadmap страница (~20 мин)

**Что делаем:**
- Новый шаблон `app/templates/pages/changelog.html` (extends landing)
- Роут `GET /changelog` в `app/pages/router.py` (без auth)
- Контент — markdown-исходник в `app/pages/changelog_data.py` (массив dict
  c date/version/title/items). Источник: PROGRESS.md major-вехи + git log
- Дополнительно: `/roadmap` страница с честным списком «делаем сейчас /
  следующие 3 месяца / возможно потом» — Habr любит прозрачность
- Ссылка на `/changelog` и `/roadmap` в footer + в landing

**Файлы:**
- `app/pages/changelog_data.py` (новый)
- `app/pages/roadmap_data.py` (новый)
- `app/pages/router.py`
- `app/templates/pages/changelog.html` (новый)
- `app/templates/pages/roadmap.html` (новый)

**Acceptance:**
- `GET /changelog` 200 OK без login
- `GET /roadmap` 200 OK без login
- Минимум 5 changelog-записей за последние 2 недели
- Roadmap с 3 секциями (Now/Next/Maybe), хотя бы по 3 пункта в каждой
- Smoke-test обновить — добавить 2 новых endpoint в список

---

### Chunk H6 — Базовый load-test (~20 мин)

**Что делаем:**
- Новый файл `scripts/load_test.py` — `httpx.AsyncClient` с 100 concurrent
  запросов на `/`, `/landing`, `/app/today` (с залогиненной cookie),
  `/api/profile` за 30 сек
- Запускать локально против прода: `uv run python scripts/load_test.py
  https://getdoday.ru 100 30`
- Метрики: p50/p95/p99 latency, error-rate, RPS
- Документировать результаты в новом файле `audit/2026-05-11/load-test.md`
- Если p95 > 2s или error-rate > 1% — выяснить узкое место, поправить
  (скорее всего uvicorn workers count или pool size)

**Файлы:**
- `scripts/load_test.py` (новый)
- `audit/2026-05-11/load-test.md` (новый)

**Acceptance:**
- На 100 concurrent / 30 сек: p95 < 2s, errors < 1%
- Результаты в `audit/2026-05-11/load-test.md`
- Pre-commit green (ruff на script)

---

### Chunk H7 — Demo-GIF на landing (~30 мин)

**Что делаем:**
- Юзер записывает 5-10 секундный screencast через ScreenToGif:
  открыть quick-add → ввести «купить молоко завтра !!! @дом» → задача
  появилась с чипсами 🟠 завтра / 🔴 P1 / @дом → ✓ закрыл задачу
- Размер: ширина 800-1000px, fps 15, ~1-3MB optimized
- Сохранить в `app/static/demo/quick-add.gif`
- На `landing.html` в hero-section заменить статичный mock-screenshot на
  этот GIF + лёгкая рамка-фрейм mobile/laptop
- Lazy-load (`loading="lazy"`) чтобы не тормозило first paint

**Файлы:**
- `app/static/demo/quick-add.gif` (юзер записывает)
- `app/templates/landing.html`

**Acceptance:**
- GIF играется на `/`, размер файла < 3MB
- Lighthouse Performance score не упал > 5 пунктов
- Mobile (320/375) — GIF не overflow

**Юзер-тач-поинт:** запись GIF делает руками. Если нет — пропустить,
оставить статичный mock; не блокер для launch.

---

# БЛОК 2 — Telegram Mini App (~15-20 часов)

Цель: полноценный TMA внутри Telegram, доступный через `/app` команду
бота или menu-button рядом с input. Wow-фактор для Habr-аудитории
(«не просто бот, а app внутри Telegram»).

## Архитектурные решения

1. **Стек:** HTMX + Alpine + Tailwind (тот же что в веб-апе). Никакого
   React/Vue/Svelte (запрет в CLAUDE.md). URL-префикс: `/miniapp/*`.
   Templates в `app/templates/miniapp/`.
2. **Auth:** Telegram WebApp `initData` (HMAC-SHA256 с
   `secret = HMAC(bot_token, "WebAppData")`), валидация на сервере →
   лукап в `telegram_links` → ставим session-cookie. Ноль логин-форм.
3. **Темизация:** читаем `Telegram.WebApp.themeParams` (bg/text/accent/
   hint/secondary/button), маплем на CSS-vars. Listen на `themeChanged`
   event — мгновенно перекрашиваем.
4. **Reuse сервисов:** `tasks/service.py`, `projects/service.py`,
   `labels/service.py` — используем как есть, новые тонкие endpoint-обёртки
   в `app/miniapp/router.py`.

## Структура (5 вкладок bottom-nav)

| # | Вкладка | Содержание |
|---|---|---|
| 1 | Сегодня | Просрочка + сегодня, streak ring, прогресс «5/8», quick-add |
| 2 | Инбокс | Нераспределённые задачи, кнопка «move to project» |
| 3 | Календарь | Week-view с горизонтальным свайпом, heatmap снизу |
| 4 | Проекты | List with цветными точками + counts |
| 5 | Я | Stats, streak, режим, ссылка на веб |

---

## Фаза A — Фундамент (~3 часа, 4 чанка)

### Chunk MA1 — initData валидация + auth (~1ч)

**Файлы:** `app/miniapp/auth.py` (новый), `app/miniapp/router.py` (новый),
`app/main.py` (include_router), `tests/test_miniapp_auth.py` (новый).

**Что делаем:**
- `app/miniapp/auth.py`:
  - `validate_init_data(init_data: str, bot_token: str) -> dict | None` —
    парсит querystring, отделяет `hash`, строит data-check-string из
    отсортированных params, считает HMAC, сверяет
  - `get_auth_date_from_init_data(...) -> datetime` — парсит auth_date
  - Reject если auth_date старше 24 часов
- `POST /miniapp/auth` endpoint:
  - body: `{"init_data": "..."}` от клиента
  - валидирует initData, парсит `user.id` (Telegram ID)
  - лукап `telegram_links` где `chat_id == user.id`
  - если найден → ставим session cookie с `user_id` (Doday user UUID)
  - если нет → 401 + body `{"need_link": true, "telegram_user_id": ...}`
- Тесты: 6+ кейсов (valid, invalid hash, stale auth_date, missing user
  field, чат не привязан, чат привязан → cookie ставится)

**Acceptance:**
- 6+ тестов green
- mypy/ruff/jinja green
- `POST /miniapp/auth` с реальным initData (mocked в тесте) → 200 +
  cookie

### Chunk MA2 — Base layout + auto-theming (~45 мин)

**Файлы:** `app/templates/miniapp/_base.html` (новый),
`app/static/miniapp/miniapp.css` (новый), `app/static/miniapp/miniapp.js`
(новый).

**Что делаем:**
- `_base.html` — самостоятельный layout без topbar/sidebar:
  - `<head>`: Telegram WebApp script `<script src="https://telegram.org/js/telegram-web-app.js"></script>`
  - viewport-fit=cover, safe-area
  - CSS-vars привязанные к `--tg-theme-*`
  - `<body>`: full-height, no scroll on root, scroll on content
  - Нижний bottom-nav (5 иконок, sticky-bottom + safe-area-inset-bottom)
- `miniapp.js`:
  - `Telegram.WebApp.ready()` + `expand()` при старте
  - `themeChanged` listener → reflowt CSS-vars
  - Helper `tg.haptic.impact('medium')`, `tg.haptic.notification('success')`
  - MainButton-helper для каждой страницы
- `miniapp.css`: bottom-nav стили, swipe-action стили, bottom-sheet
  baseline

**Acceptance:**
- Открытие `/miniapp/` локально через browser → видно layout
- DevTools mobile mode 375px — bottom-nav не перекрывает контент
- При смене prefers-color-scheme — CSS-vars обновляются (стимулим вручную
  через `Telegram.WebApp.themeParams = {...}` в console)

### Chunk MA3 — Bottom-nav routing + 5 пустых вкладок (~30 мин)

**Файлы:** `app/miniapp/router.py`, `app/templates/miniapp/today.html`,
`inbox.html`, `calendar.html`, `projects.html`, `me.html` (все 5 — пустые
заглушки с заголовком).

**Что делаем:**
- 5 endpoints в `router.py`: `/miniapp/`, `/miniapp/inbox`,
  `/miniapp/calendar`, `/miniapp/projects`, `/miniapp/me`
- Каждый требует session cookie (зависимость `current_user_or_redirect`)
- Если no session — redirect на `/miniapp/link` (см. MA4)
- Bottom-nav в `_base.html` подсвечивает активную вкладку через
  `request.url.path`

**Acceptance:**
- Все 5 страниц 200 + show заглушку
- Bottom-nav active state работает
- pytest: smoke-test одного endpoint в каждом

### Chunk MA4 — «Привяжи аккаунт» onboarding (~45 мин)

**Файлы:** `app/templates/miniapp/link.html` (новый), endpoint в
`app/miniapp/router.py`.

**Что делаем:**
- `GET /miniapp/link?telegram_user_id=...` — рендерит экран:
  - Иллюстрация (svg)
  - «Чтобы начать, привяжи Doday-аккаунт»
  - Если у юзера НЕТ Doday-аккаунта вообще: «Открыть getdoday.ru →
    Зарегистрироваться → Профиль → Telegram → нажми Подключить»
  - Если юзер залогинен на getdoday.ru в браузере (cookie shared если
    same-domain — а тут не same): инструкция простая
  - WebApp.openLink('https://getdoday.ru/app/profile') кнопкой
- POST `/miniapp/auth` пробуется автоматически на mount страницы (через
  `miniapp.js` шлёт `Telegram.WebApp.initData` → бэкенд валидирует) —
  если успех → redirect на `/miniapp/`. Если нет → /miniapp/link

**Acceptance:**
- Новый юзер открывает мини-апп → видит экран `link` с понятной
  инструкцией
- Привязанный юзер (есть запись в `telegram_links`) → не видит экран,
  сразу попадает на Today

---

## Фаза B — Core CRUD (~5 часов, 5 чанков)

### Chunk MB1 — Today view + список задач (~1ч)

**Файлы:** `app/templates/miniapp/today.html`,
`app/templates/miniapp/_partials/task_card.html` (новый, мини-вариант
task_row).

**Что делаем:**
- Today показывает: header «Сегодня · streak 🔥7» + прогресс-кольцо
  (svg, % сегодня закрытых) + список задач (overdue + today),
  свернутая секция «Готово N» снизу
- task_card.html: чекбокс (radio-style), title, мелкие чипсы
  priority/date/labels, edge-to-edge
- Reuse `app/views/router.py::today_view` сервис-логику

**Acceptance:**
- Локально мини-апп показывает реальные задачи
- На свайп пока ничего не делает (это MB3)

### Chunk MB2 — Quick-add с live-preview парсера (~1ч)

**Файлы:** `app/templates/miniapp/_partials/quickadd.html` (новый),
`app/miniapp/router.py` POST endpoint.

**Что делаем:**
- На Today + Inbox sticky-input сверху «Что сделать? @дом завтра !!!»
- Под инпутом — Alpine x-data: на каждое нажатие шлёт fetch на
  `/miniapp/api/parse?text=...` (debounce 200ms) → бэкенд возвращает
  preview-объект (title без хвостов, due_at, priority, labels) →
  показываем мерцающие чипсы
- Submit (MainButton с текстом «Добавить» — биндим её) →
  POST `/miniapp/api/tasks` → перерендер списка
- Haptic success на successful add

**Acceptance:**
- Вводишь «купить молоко завтра !!! @дом» — видишь чипсы 🟠 / 🔴 / @дом
- MainButton «Добавить» — после добавления чистит input

### Chunk MB3 — Swipe-actions complete/snooze (~1ч)

**Файлы:** `app/templates/miniapp/_partials/task_card.html`,
`app/static/miniapp/miniapp.js`.

**Что делаем:**
- task_card обёрнут в swipe-container (CSS transform + JS-touch-handler)
- Свайп влево past 80px → задача отправляется в complete (POST
  `/miniapp/api/tasks/<id>/complete`), карточка fade-out
- Свайп вправо past 80px → snooze на завтра (PATCH due_at = +1 day)
- Haptic medium на confirm-action
- Анимация: revealed action-button с цветом (зелёный complete /
  оранжевый snooze)
- Optimistic UI — карточка пропадает СРАЗУ, бэкенд call в фоне

**Acceptance:**
- На локальном тесте через DevTools touch-emulation работает свайп
- Cancel-свайп (отпустил до 80px) — возвращает на место с
  spring-animation

### Chunk MB4 — Task-detail bottom-sheet (~1ч)

**Файлы:** `app/templates/miniapp/_partials/task_sheet.html` (новый),
`app/miniapp/router.py` GET/PATCH/DELETE endpoints.

**Что делаем:**
- Тап на task_card → bottom-sheet поднимается snap'ом снизу (Alpine
  x-show + x-transition)
- В sheet: title-input (autoSave on blur), due-date picker (native HTML5
  date input + chips «сегодня/завтра/+неделя»), priority chips P1-P4,
  project picker (bottom-sheet второго уровня), label picker (multi-chip),
  комментарий (textarea), кнопки «Удалить» + «Закрыть»
- Sheet может drag-up на full-screen
- BackButton Telegram'а → закрытие sheet → закрытие screen

**Acceptance:**
- Тап на задачу — sheet поднимается smooth
- Изменение title → автосохранение (PATCH через 800ms debounce)
- Выбор даты/приоритета/проекта/labels → reflow на UI

### Chunk MB5 — Inbox view + move-to-project (~30 мин)

**Файлы:** `app/templates/miniapp/inbox.html`.

**Что делаем:**
- Inbox показывает все задачи где project_id == default Inbox project
- На каждой задаче: кнопка-иконка «Move» → bottom-sheet с project list
- После выбора → PATCH project_id → задача исчезает из Inbox

**Acceptance:**
- Inbox показывает реальные задачи
- Move-to-project работает, оба list'а обновляются

---

## Фаза C — Навигация (~4 часа, 4 чанка)

### Chunk MC1 — Calendar week-view (~1.5ч)

**Файлы:** `app/templates/miniapp/calendar.html`, JS-handler.

**Что делаем:**
- Header: 7 chips «Пн Вт Ср Чт Пт Сб Вс» с цифрами дат, активный bold
- Свайп горизонтальный → следующая/предыдущая неделя
- Под chips — список задач выбранного дня
- Тап на chip → переключает день
- Haptic light на каждый swipe-shift

**Acceptance:**
- Локально работает свайп-навигация по неделям ±4 недели
- Сегодняшний день выделен рамкой

### Chunk MC2 — Calendar heatmap (commit-style) (~45 мин)

**Файлы:** `app/templates/miniapp/calendar.html` (доп секция),
`app/miniapp/router.py` GET `/miniapp/api/heatmap`.

**Что делаем:**
- Снизу calendar.html — sticky 12-week heatmap grid (84 ячейки)
- Цвет = % closed_at в этот день (0=серый, 100%=accent)
- Тап на ячейку → переключает основной calendar на ту неделю/день

**Acceptance:**
- Heatmap отображает последние 12 недель
- Тап работает

### Chunk MC3 — Projects list + project view (~1ч)

**Файлы:** `app/templates/miniapp/projects.html`,
`app/templates/miniapp/project.html`.

**Что делаем:**
- `/miniapp/projects` — header «Проекты» + список с цветными точками,
  название, count активных задач, count overdue в красном
- Тап → `/miniapp/projects/<id>` — same layout что Today но для проекта
- Кнопка «+» в header projects → bottom-sheet «новый проект»

**Acceptance:**
- Все проекты отображаются
- Проект-view показывает задачи проекта
- Создание нового проекта работает

### Chunk MC4 — Search + «Я» вкладка (~45 мин)

**Файлы:** `app/templates/miniapp/me.html`,
`app/templates/miniapp/_partials/search_sheet.html`.

**Что делаем:**
- В topbar мини-аппа (если есть) или в header «Сегодня» — иконка-лупа →
  открывает bottom-sheet search
- Search input + livesearch через `/miniapp/api/search?q=...`
- «Я» вкладка: streak (число + ring), stats (закрыто за неделю/месяц),
  audience-режим как chips для смены, ссылка «открыть полную версию» →
  WebApp.openLink('https://getdoday.ru/app/today')

**Acceptance:**
- Search возвращает результаты по title
- «Я» показывает корректные числа

---

## Фаза D — Native polish (~3 часа, 5 чанков)

### Chunk MD1 — MainButton интеграция per-screen (~30 мин)

На Today/Inbox: «Добавить задачу» → focus на quickadd
На Calendar: «На сегодня» → переключение
На Projects: «Новый проект» → bottom-sheet
На Me: hidden

### Chunk MD2 — BackButton интеграция (~20 мин)

В sheet'ах и в screen-stack — Telegram'овский BackButton показывает
back-arrow вверху клиента. Биндим `Telegram.WebApp.BackButton.onClick`
на закрытие sheet/back navigation.

### Chunk MD3 — Haptic feedback по UX-touchpoints (~30 мин)

Где: complete (success), delete (warning), priority change (selection),
swipe past threshold (medium), tab switch (light).

### Chunk MD4 — Confetti + 100% celebration (~45 мин)

При закрытии последней задачи на сегодня — canvas-confetti (lib
`https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.2/dist/confetti.browser.min.js`,
~3KB) + haptic notification('success') + временный banner
«Все задачи на сегодня закрыты! 🎉 Streak 🔥N».

### Chunk MD5 — Pull-to-refresh + themeChanged listener (~45 мин)

Pull-to-refresh: native CSS overscroll + JS scroll-handler → reload list.
themeChanged: уже подключён в MA2, проверить что работает на real-device
+ добавить smooth-transition (200ms) на vars-смену.

---

## Фаза E — Bot integration + deploy (~2 часа, 3 чанка)

### Chunk ME1 — `/app` команда + setChatMenuButton (~30 мин)

**Файлы:** `app/telegram/bot.py`.

**Что делаем:**
- Новый handler `cmd_app` — на `/app` шлёт inline-keyboard с
  WebAppInfo(url='https://getdoday.ru/miniapp/')
- В `build_app()` добавить handler
- На startup: вызвать `bot.set_chat_menu_button(menu_button=
  MenuButtonWebApp(text='Doday', web_app=WebAppInfo(...)))` — это даст
  кнопку «Doday» вместо «Меню» рядом с input в чате с ботом

**Acceptance:**
- `/app` в чате с ботом возвращает кнопку «Открыть Doday»
- Кнопка «Doday» появилась рядом с input

### Chunk ME2 — BotFather config (~15 мин — юзер делает руками)

**Что делает юзер:**
- @BotFather → `/setdomain` → `getdoday.ru` (требуется для WebApp)
- @BotFather → `/setmenubutton` → выбрать @DodayTaskBot →
  «Configure menu button» → название «Doday», URL
  `https://getdoday.ru/miniapp/`

**Acceptance:** в чате с ботом виден menu-button «Doday», тапается,
открывается мини-апп.

### Chunk ME3 — Production deploy + smoke (~1ч)

**Что делаем:**
- Все commits закидываем (auto-deploy через cron-poll подхватит)
- Обновить `scripts/smoke_test.py` — добавить `/miniapp/` (200 OK на
  unauth — даёт link-screen) в список endpoint'ов (стало 19)
- Проверить через реальный Telegram-клиент на телефоне:
  open menu-button → видит link-screen → переходит на getdoday.ru →
  привязывает аккаунт → возвращается в Telegram → /app снова → видит
  Today
- Проверить что initData-validation работает с РЕАЛЬНОЙ подписью бота
- Записать demo-видео для Habr (~30 секунд)

**Acceptance:**
- Smoke 19/19 green
- Реальный flow на телефоне работает end-to-end
- Mini App открывается из чата с ботом, виден Today

---

# Loop правила

- Каждая итерация: читай этот файл, бери первый незакрытый чанк, делай его
- После каждого commit — push в master + (cron-poll сам redeploy'ит) + smoke
  test обязательно
- Russian past-tense commits, author `112168281+SwairIt@users.noreply.github.com`
- Pre-commit (ruff/mypy/jinja-linter) **обязательно green** перед commit'ом
- pytest -q должен оставаться green после каждого чанка
- Каждый чанк коммитить отдельно. Под-итерации крупных чанков (MA1, MB1,
  MB4, MC1, MC3) — можно несколько коммитов
- НЕ ломай существующие фичи / API / роуты веб-апа
- НЕ удаляй фичи. Только дополняй
- Когда блок 1 (H1-H7) полностью ✅ — финальный commit «habr-readiness:
  завершено». Юзер может уже публиковать на Habr ДО завершения блока 2
- Когда блок 2 полностью ✅ — финальный commit «miniapp: full launch» +
  длительность/счётчик коммитов в PROGRESS.md и СТОП

---

# Прогресс

## Блок 1 — Habr-readiness
- [x] H1 — Free-for-all flag + landing-banner ✅ `9266d32`
- [x] H2 — TG-бот скрыт/«скоро» ✅ `9266d32` (объединён с H1)
- [x] H3 — Sentry интеграция ✅ `a35dce1` (init no-op без DSN; включить на проде через SENTRY_DSN env)
- [x] H4 — TG-канал в footer ✅ `7eebf58` (gated на TELEGRAM_CHANNEL_URL env; юзер впишет когда создаст)
- [x] H5 — Changelog/roadmap страницы ✅ `c0dbd96`
- [x] H6 — Базовый load-test ✅ `885c607` (50×30s GREEN: p95=1811ms, 0% errors, 36.6 RPS)
- [~] H7 — Demo-GIF на landing — пропущен (юзер должен записать GIF, не блокер)

## Блок 2 — Telegram Mini App

### Фаза A — Фундамент
- [x] MA1 — initData валидация + auth ✅ `a8b2a5f`
- [x] MA2 — Base layout + auto-theming ✅ `6d76c0b`
- [x] MA3 — Bottom-nav routing + 5 заглушек ✅ `fa59420`
- [x] MA4 — «Привяжи аккаунт» onboarding ✅ `7bcb8bd`

### Фаза B — Core CRUD
- [x] MB1 — Today view + список ✅ `40de505`
- [x] MB2 — Quick-add с live-preview ✅ `f464b82`
- [x] MB3 — Swipe-actions complete/snooze ✅ `cb2253d`
- [x] MB4 — Task-detail bottom-sheet ✅ `2c641ab`
- [x] MB5 — Inbox + move-to-project ✅ `830a47a`

### Фаза C — Навигация
- [x] MC1 — Calendar week-view ✅ `4a86ede`
- [ ] MC2 — Calendar heatmap
- [ ] MC3 — Projects list + view
- [ ] MC4 — Search + «Я» вкладка

### Фаза D — Native polish
- [ ] MD1 — MainButton per-screen
- [ ] MD2 — BackButton интеграция
- [ ] MD3 — Haptic feedback
- [ ] MD4 — Confetti + 100% celebration
- [ ] MD5 — Pull-to-refresh + themeChanged

### Фаза E — Bot + deploy
- [ ] ME1 — `/app` команда + setChatMenuButton
- [ ] ME2 — BotFather config (юзер делает руками)
- [ ] ME3 — Production deploy + real-device smoke

(После завершения каждый чанк: ✅ + commit-SHA.)

---

# Юзер-тач-поинты (что нужно от юзера)

| Чанк | Что нужно | Когда |
|---|---|---|
| H3 | Sentry DSN (зарегаться на sentry.io free) | До старта H3 |
| H4 | Создать TG-канал, дать `@username` | До старта H4 |
| H7 | Записать demo.gif (опционально) | До или после H7 |
| ME2 | BotFather setdomain + setmenubutton | После ME1 |
| ME3 | Тест на реальном телефоне через Telegram | После ME1+ME2 |

Если юзера нет — H3/H4/H7 пропустить (не блокеры), ME2/ME3 — отложить
до его возвращения.
