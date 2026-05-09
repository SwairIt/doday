# Overnight loop plan — 3 tasks

**Date:** 2026-05-09 night
**Mode:** autonomous loop, cron interval, English internal docs
**Russian commits, SwairIt author email**

## Что должно быть сделано к утру

3 чанка в порядке (нельзя менять — email-дайджест зависит от стабильного
state, его в самом конце; landing-fix самый быстрый — первым).

### Chunk 1 — Landing pricing-card Free контент-фикс (~15 минут)

`app/templates/landing.html` блок `#pricing` карточка «Free» содержит
устаревшую информацию о лимитах. Источник правды:
`app/billing/service.py::TIERS["free"]`.

**Что сделать:**

1. Прочитать `app/billing/service.py` и выписать актуальные лимиты для tier
   `free` (max_projects, max_filters, имеется ли kanban, имеется ли activity,
   trial-логика).
2. В `app/templates/landing.html` найти pricing-block (`#pricing` или
   аналогичный — поищи по «Free» / «299 ₽» / «Доступно бесплатно»). Сравни
   что там написано с реальностью в коде. Возможные расхождения:
   - «До 5 проектов» vs реально 10 (или сколько в TIERS)
   - «Канбан недоступен» vs реально включён во Free
   - «Кастомные фильтры недоступны» vs реально 3 во Free
   - «Активность недоступна» vs реально включена
   - «14-дневный Pro trial» — есть в коде или нет? проверь
     `app/billing/service.py` на наличие trial-логики
3. Обнови HTML под реальность. **Никаких приукрашиваний** — пиши то что
   реально доступно. Если в коде написано «10 проектов» а на лендинге
   «безлимит», ставь «10 проектов».
4. `pre-commit run --files <изменённый.html>` → ruff (skipped) + jinja
   linter Passed.
5. Russian past-tense commit «исправил pricing-карточку Free на лендинге —
   привёл к реальным лимитам из TIERS["free"]».
6. Push в master (TOKEN из .env).
7. Redeploy через `.tmp_ssh_inspect.py`. Внешняя smoke-проверка 18/18 green.
8. Отметь чанк ✅ в этом файле.

### Chunk 2 — Help articles контент-аудит (~1-2 часа)

`app/help/articles.py` содержит 22 статьи. После ребрендинга, 19 миграций,
изменений UI и роутов — некоторые статьи могут ссылаться на старые
имена/маршруты/поля.

**Что сделать:**

1. Прочитать весь `app/help/articles.py` (он должен быть один большой
   список dict-ов с slug/title/body/section).
2. Для каждой статьи (всего 22) проверить:
   - Упоминаемые маршруты (`/app/<что-то>`) — все существуют в
     `app/views/router.py` или `app/main.py`? Если упоминается
     `/app/inbox` — проверить что redirect живой. Если `/app/projects/<X>`
     — что есть проект-view.
   - Имена UI-элементов: «нажмите кнопку Профиль» — но если это сейчас
     «Настройки», обнови.
   - Скриншоты / placeholder'ы: если ссылаются на изображение которого нет
     — заменить или убрать упоминание.
   - Использование актуальной brand-фразы «Doday» (а не SchoolTodo /
     старого имени). Если есть «SchoolTodo» где-то в тексте — replace.
   - Терминология: «школьник» → нейтральное где возможно (audience-
     неутрально), но если статья СПЕЦИФИЧНА для school-audience — оставить.
   - Hotkeys: если упоминается «Cmd+K» — проверь что в `task_keyboard.html`
     это всё ещё действующий хоткей.
   - Фичи: упоминается «помодоро» — есть в коде? «граф связей» — есть?
     «время-трекер» — есть? Все должны быть в актуальном коде.
3. Веди список найденных косяков в комментарии к коду или временный markdown.
4. Правь по месту. Если статья радикально устарела — выкинь её, добавь в
   её место TODO-комментарий «article removed 2026-05-09, был о
   <тема>, переписать когда будет повод».
5. После каждой группы из 5-8 правок — отдельный commit.
6. После всех правок: pre-commit + smoke-test, redeploy, проверь 2-3 живые
   статьи через curl `/help/<slug>` 200.
7. Отметь чанк ✅.

### Chunk 3 — Email-дайджест MVP (~3-4 часа)

Top-1 запрашиваемая фича пред-launch. Утренний email с задачами на день.

**Что должно работать:**

- Юзер с подтверждённым email и opt-in флагом получает в 7:00 МСК
  ежедневный email с:
  - Topic line: «Twoy plan na <дата>: N задач»
  - Список задач на сегодня (overdue + сегодня + первые 3 завтрашние)
  - 1-2 строки motivational copy под audience (school/company/personal)
  - Footer с ссылкой «Отписаться от утренних писем»
- Opt-in setting на `/app/profile` — toggle «Получать утренний дайджест в
  7:00 МСК». По умолчанию OFF (юзер должен явно включить).
- Endpoint `POST /api/digest/send-now` (admin-only or self-only) — для
  ручного теста.
- Cron: на проде через системный cron (на сервере getdoday.ru), каждый
  день в 7:00 МСК → curl `POST /api/digest/cron-trigger?token=<secret>`
  → бэкенд циклит по юзерам с opt-in и шлёт.

**Архитектура:**

1. Миграция `0021_user_morning_digest`: добавить колонку
   `users.morning_digest_enabled BOOLEAN NOT NULL DEFAULT FALSE` +
   `users.morning_digest_last_sent_at TIMESTAMPTZ NULL` (для дедупа).
2. Pydantic schema в `app/profile/schemas.py` для toggle.
3. Endpoint `PATCH /api/profile/morning-digest` — set true/false.
4. UI в `app/templates/app/profile.html` — toggle-row рядом с
   reminders / calendar-subscription секциями. Объясни что в 7:00 МСК.
5. Новый модуль `app/digest/`:
   - `service.py::compose_digest_for(user) -> str` — собирает HTML+text
     версии письма
   - `service.py::send_morning_digests() -> int` — итерируется по юзерам
     с `morning_digest_enabled=True`, шлёт через aiosmtplib (как auth/email),
     обновляет `last_sent_at`. Возвращает кол-во отправленных.
   - `router.py`: `POST /api/digest/send-now` (self-only),
     `POST /api/digest/cron-trigger` (с проверкой
     `request.headers.get('X-Cron-Token') == settings.cron_token`).
6. Email template в `app/digest/templates/morning.html` (HTML, inline-CSS
   для совместимости с GMail/Yandex).
7. Plain-text fallback `app/digest/templates/morning.txt`.
8. Тесты в `tests/test_digest/`:
   - test_compose_digest — собирает HTML/text, проверяет что заголовки
     задач в результате
   - test_endpoints — POST /send-now с auth → 200, без auth → 401
   - test_cron_trigger — без X-Cron-Token → 403, с правильным → 200 +
     стрельнул на N юзеров
   - test_opt_in_toggle — PATCH /api/profile/morning-digest
9. Setup cron на проде через SSH: добавить crontab line
   `0 4 * * * curl -sS -X POST -H "X-Cron-Token: <secret>" http://127.0.0.1:8011/api/digest/cron-trigger >> /tmp/digest-cron.log 2>&1`
   (4 UTC = 7 МСК).
10. Добавить `cron_token: str = ""` в `app/config.py`. На проде в `.env` —
    32-байтный secret. Скрипт `.tmp_ssh_set_cron_token.py` для записи.
11. Документация в `docs/CONTRIBUTING.md` или `DEPLOY.md` — раздел «Cron-
    задачи», список текущих cron-jobs на проде.

**После завершения:**

- pre-commit (ruff/mypy/jinja) Passed
- pytest на новом модуле — все тесты зелёные
- smoke-test 18/18 (новые endpoint'ы НЕ в smoke-list по умолчанию, не
  ломаем baseline)
- Redeploy
- Из своего тестового аккаунта (`responsive-test@doday.local` или
  `yarik@doday.app`): включи opt-in на /app/profile, дёрни
  `POST /api/digest/send-now` через curl с cookie, проверь что письмо
  приходит на нашу dev SMTP (или на prod если SMTP_* заполнены — вряд ли).
- В docker отдельно НЕ нужно — uvicorn на проде так и работает.
- Отметь чанк ✅.

## Loop правила

- Каждая итерация: прочитать этот файл, найти первый незакрытый чанк,
  взяться за него.
- Если чанк большой (Chunk 3) — разбить на под-итерации (миграция →
  schema/endpoint → UI → тесты → deploy → cron-setup). Между под-
  итерациями коммит и push.
- После каждого commit: push в master через TOKEN, redeploy
  `.tmp_ssh_inspect.py`, smoke-test 18/18, отметь прогресс в этом файле
  и в PROGRESS.md.
- Если упёрся в конкретный block (нужна интеракция с юзером) — отметь в
  этом файле как **BLOCKED**, переходи к следующему чанку.
- Когда все 3 ✅ — финальный commit «overnight loop: 3 чанка завершены»
  + financial summary в PROGRESS.md (длительность, количество коммитов).
- **Не трогать архитектуру кроме того что нужно для чанка.** Это полировка,
  не рефакторинг.
- **Не отключать тесты, не игнорировать lint warnings.** Если упало —
  чинь до зелёного.
- Author email **ВСЕГДА** `112168281+SwairIt@users.noreply.github.com`.

## Прогресс

- [x] Chunk 1 — Landing pricing fix ✅ `6ef8aae`
- [ ] Chunk 2 — Help articles audit
- [ ] Chunk 3 — Email digest MVP

(Каждый чанк должен быть отмечен ✅ + commit-SHA после завершения.)
