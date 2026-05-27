# READ-FIRST · контекст для нового проекта

> **Кому это:** если юзер написал «прочти READ-FIRST и придумай новый проект» —
> ты в правильном месте.
>
> **Что внутри:** профиль юзера, его цели и ограничения, список уже существующих
> проектов (чтобы не дублировать), технические решения известных проблем
> (чтобы быстрее делать), правила workflow.
>
> **После создания своего проекта — обнови раздел «Существующие проекты»**
> (см. инструкцию в конце файла). Каждый новый Opus делает один проект и
> записывает его сюда, чтобы следующие не запутались.

---

## 1. Кто юзер

- **Зовут:** Ярослав. GitHub: [@SwairIt](https://github.com/SwairIt). Email для коммитов:
  `112168281+SwairIt@users.noreply.github.com` (НЕ system-git-email!). Личная почта
  `bugdenes@gmail.com`.
- **15 лет.** Российский indie-dev, школьник.
- **Stack:** сильный Python/FastAPI/Postgres. JS — слабее (так что подробно объясняй
  про frontend, не «само понятно»).
- **Стиль работы:** любит автономию, говорит «сам всё реши, не тревожь меня». Это
  не значит халтурить — это значит делать качественно без бесконечных уточнений.
  Тратит много часов на проект, спокойно работает ночами.
- **Контакты:** public-email для проектов `doday.support@gmail.com` (НЕ личный!).

## 2. Цели и стратегия

- **Главная цель:** заработать деньги. Желательно быстро.
- **НО:** «я люблю делать проекты». Значит стратегия — **много малых
  продуктов под брендом Doday Studio**, а не «один идеальный гигант».
- **Каждый chat = новый проект.** Не пытайся продолжать чужие проекты —
  работай только над своим, обновляй раздел 3 этого файла когда закончил.
- **Юр.форма:** физлицо/самозанятый. **Поэтому платёжный канал — Telegram Stars**
  (не требует ИП, ОКВЭД, расчётного счёта). Все продукты должны уметь
  принимать Stars если монетизируются.
- **Аудитория:** РФ. Русский интерфейс, русская поддержка, хостинг РФ.

## 3. Существующие проекты (НЕ дублировать!)

| Проект | URL | Бот | Статус | Что делает |
|---|---|---|---|---|
| **Doday Tasks** | `getdoday.ru` | `@DodayTaskBot` | production | Todoist-style todo-list + команды |
| **Lessio** | `getdoday.ru/lessio` | `@mylessiobot` | pre-launch ready | Booking + Stars-оплата для соло-учителей |
| **Razbery (Doday Q&A)** | `getdoday.ru/qa/` | — | **live MVP** | Школьное Q&A с разборами (5–11 класс), 665+ seed-вопросов, SEO-driven рост |
| **Tap Tower** | `getdoday.ru/taptower` | (тот же DodayTaskBot) | live | Telegram Mini App игра. Port 8012, **не трогать** |
| **IndigoSmart** | port 8000 (отдельно) | — | live | **Не трогать** — отдельный проект |
| **School diary parser** | внутри Doday | — | unfinished | Парсер Школьного портала МО + МЭШ. Endpoints нужно поправить через live-token + DevTools capture |

### Подробнее по флагманам

**Doday Tasks** — pivot 2026-05-13: focused Todoist-style + командная работа.
**Намеренно убраны** (НЕ возвращай): gamification, achievements, habits, mood,
time-tracking. Все pivot-решения в `git log --grep "simplify"`. Стартовое
наполнение — auth.service starter-tasks на русском.

**Lessio** — pivot Phase 3 закончен 2026-05-26. Содержит: публичная страница
`/u/<slug>`, услуги, расписание, booking-flow, Telegram Stars + manual-оплата,
help-center (28 статей), блог (18 long-form), 5 SEO niche-landings, custom 404,
RSS-feed, onboarding-чеклист, floating help-bubble. **Готов к тестовой
аудитории 100-300 человек.** Что осталось — в `docs/YOUR-LAUNCH-PLAN.md`
(DNS Resend, Better Stack, Sentry alerts, @BotFather аватарка, real Stars-test).

**Razbery (Doday Q&A)** — флагман на `getdoday.ru/qa/`, запущен 2026-05-28.
Школьный StackOverflow: 16 предметов × 5-11 классов, anti-cheating механика
(обязательное «Объяснение» ≥150 знаков), репутация, голосование, sitemap.
**665+ seed-Q&A** уже на проде, ещё ~9 предметов догружаются по мере
готовности параллельных агентов. Stars-tips и Pro-tier заложены в schema
но скрыты до phase-2. Spec: `docs/superpowers/specs/2026-05-28-doday-qa-design.md`,
plan: `docs/superpowers/plans/2026-05-28-doday-qa-overnight.md`.

### Идеи для нового проекта (НЕ обязательно, можешь свою)

Когда юзер просит «придумай проект» — варианты в духе Doday Studio:

- 💰 **Anketa** — анкета-портфолио для фрилансеров (как Linktree но с приёмом
  оплаты Stars за консультацию)
- 📓 **Daypage** — публичный дневник (как Substack но для коротких заметок,
  без подписки на email — просто публичный)
- 🍳 **Recepty** — recipe-bookmarking + meal-planning (личный или общий)
- 🎓 **Examready** — генератор учебных тестов из текста (для подготовки к
  экзаменам, без AI cheating — наоборот, помощник *учить*)
- 🗓 **Sobytie** — анонимные RSVP к локальным событиям (concerts, meetups)
  без регистрации
- 🧮 **Calcer** — встраиваемый калькулятор для рекламы услуг (риелтор: «сколько
  стоит ипотека», репетитор: «сколько занятий до B2»)
- 📈 **Trackr** — простой habit-tracker как анти-Streaks (фокус на streaks без
  моральных лекций)

Спроси юзера какая нравится или предложи свою. **Главное** — должна
монетизироваться через Stars, занимать одну-две недели максимум, не дублировать
существующие.

## 4. Tech-stack и среда разработки

### Локалка (Windows)

- **OS:** Windows Server 2019. Shell: PowerShell (default) + Bash (через Git Bash).
- **WD:** `c:\www-Yaroslav\SchoolProject` (monorepo)
- **Python:** 3.13 + `uv` для venv. Активация: `uv sync`.
- **Запуск:** `uv run uvicorn app.main:app --reload` (uvicorn на :8000 локально)
- **Тесты:** `uv run pytest tests/ -k "feature_name" --tb=line -q`
- **Lint:** ruff + mypy `--strict`. Pre-commit hook блокирует bad-commits.

### Продакшн (FastPanel-managed VPS)

- **Host:** `getdoday.ru`, SSH-user `getdoday@getdoday.ru`
- **App-dir:** `/var/www/getdoday/data/www/getdoday.ru/app`
- **`.env`:** `/var/www/getdoday/data/www/getdoday.ru/app/.env`
- **Uvicorn:** port `8011` (Doday + Lessio one process)
- **Bot worker:** отдельный процесс, `/var/www/getdoday/data/start-bot.sh`, PID
  в `/var/www/getdoday/data/bot.pid`
- **Logs:** `/var/www/getdoday/data/logs/{bot,deploy-poll,...}.log` +
  `/tmp/*.log` (cron'ы пишут туда)
- **Backups:** `/var/www/getdoday/data/backups/doday-YYYY-MM-DD_HHMM.sql.gz`
  (cron 30 4 * * *, retention 7 daily)

### Auto-deploy

Push на `github.com/SwairIt/doday` master → `deploy-poll.sh` (cron каждую минуту)
делает `git reset --hard origin/master` + `uv sync` + `alembic upgrade head` +
kill PID на :8011 + restart uvicorn.

⚠️ **Gotcha:** deploy-poll exit'ит если `LOCAL == REMOTE` уже, поэтому **не
рестартит uvicorn если кто-то уже подтянул код вручную** — в этом случае нужен
manual restart (см. ниже).

### Stack по умолчанию

- **Backend:** FastAPI, async SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2
- **Auth:** session-cookie через `app.auth.deps` (`CurrentUser`/`RequiredUser`)
- **Frontend:** Jinja2 + Tailwind CDN + Alpine.js + HTMX (no build step)
- **Logging:** structlog → Sentry auto-capture
- **Email:** Resend SMTP (`smtp.resend.com:587`)
- **DB:** managed PostgreSQL (remote). **НИКОГДА** не создавай local PG —
  используй существующий managed instance через `DATABASE_URL` в `.env`.
- **Payments:** Telegram Stars через `app.billing.stars` (HMAC-signed payload)
- **Bots:** `python-telegram-bot 21.x`, single worker = 2 Application'а в одном
  loop через `asyncio.gather`

## 5. Решения известных проблем (для скорости)

### 🔴 Bot не подключается к api.telegram.org

**Симптом:** `ERROR doday.telegram: ... Timed out`.

**Причина:** DNS на проде отдаёт `149.154.166.110` который заблокирован
провайдером (RKN/firewall). Только `149.154.167.220` работает с этого VPS.

**Решение** — уже в коде `app/telegram/bot.py:_make_telegram_request`:
custom `HardcodedIPBackend(httpcore.AutoBackend)` override'ит `connect_tcp`
для api.telegram.org → реально connects к `.167.220`. SSL handshake уровнем
выше с `server_hostname=api.telegram.org` → cert валиден.

Если API IP сменится — обнови `_TELEGRAM_API_IPS` в bot.py + test через
`bash -c "echo > /dev/tcp/<ip>/443"` на проде.

### 🟡 Deploy не рестартит uvicorn

**Симптом:** push на master, ждёшь deploy-poll, через минуту prod на старом SHA.

**Причина:** `LOCAL == REMOTE` уже (например, ты сам git pull сделал на проде).

**Решение:** manual restart через SSH —
```bash
SSH_PASS=$(grep '^SSH_PASS=' .env | cut -d= -f2- | tr -d '\r\n')
HOSTKEY="SHA256:NwU1dGS29JAjs2K5LfEtu3DLFgg04yo7ZEA4iOGkM6E"
plink -batch -ssh -hostkey "$HOSTKEY" -pw "$SSH_PASS" getdoday@getdoday.ru \
  "for pid in \$(lsof -ti:8011 2>/dev/null); do kill -9 \$pid; done; \
   sleep 1; python3 /var/www/getdoday/data/start_uvicorn.py; \
   sleep 3; curl -s http://127.0.0.1:8011/version"
```

### 🟡 Pydantic settings не парсит пустую строку

**Симптом:** `ValidationError: Input should be a valid boolean, unable to interpret input ''`.

**Причина:** для `bool`-полей в pydantic-settings пустая строка ≠ False.
Должно быть `0/1/true/false`.

**Решение:** на проде `.env` всегда указывай явно — `DISABLE_TELEGRAM_IPV4_PATCH=0`
не `DISABLE_TELEGRAM_IPV4_PATCH=`.

### 🟡 Alpine.js apostrophe-trap

**Симптом:** `x-data="{ emoji: '{{ user_var }}' }"` → весь Alpine-компонент
ломается если `user_var` содержит `'`.

**Решение:** используй `tojson` filter:
```jinja
x-data='{ "emoji": {{ (user_var or "default") | tojson }} }'
```

### 🟡 htmx + Alpine динамические формы

**Симптом:** Alpine-генерированная форма с `hx-post` не работает — htmx делает
GET-запрос вместо POST.

**Решение:** для динамических forms используй `<form>` с explicit `fetch().then(...)`
в Alpine handler'е, не полагайся на `hx-post`-инициализацию.

### 🟡 Pytest concurrency

**Симптом:** deadlock в conftest при `drop_all/create_all`.

**Решение:** НЕ запускай две pytest-сессии одновременно. Если orphan pytest
процесс висит — `taskkill /F /IM python.exe` (Windows) и
`psql ... -c "select pg_terminate_backend(pid) from pg_stat_activity ..."`.

### 🟡 PowerShell file-write gotchas

**Симптом:** Bash-команды `cut`, `sed` ломаются на файле, который PowerShell
писал.

**Причина:** `Set-Content -Encoding utf8` добавляет BOM; default `Out-File`
пишет CRLF.

**Решение:** для cross-tool текстовых файлов используй `Write` (мой Write
tool), он пишет UTF-8 без BOM с LF.

### 🟡 Git author email

**ВСЕГДА** использовать `112168281+SwairIt@users.noreply.github.com` (это
SwairIt's GitHub no-reply email). Иначе коммиты не привязываются к
SwairIt-аккаунту → не видны в его profile contributions.

```bash
git -c user.email="112168281+SwairIt@users.noreply.github.com" \
    -c user.name="SwairIt" \
    commit -m "..."
```

### 🟡 Push через token

Token в `.env`:
```bash
TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
git push "https://x-access-token:${TOKEN}@github.com/SwairIt/doday.git" master
```

**НЕ** читай `.env` целиком и **НЕ** echo'й его контент — там есть SSH_PASS,
DB-пароль, SENTRY_DSN, TELEGRAM_BOT_TOKEN.

### 🟢 SSH на прод

```bash
SSH_PASS=$(grep '^SSH_PASS=' .env | cut -d= -f2- | tr -d '\r\n')
HOSTKEY="SHA256:NwU1dGS29JAjs2K5LfEtu3DLFgg04yo7ZEA4iOGkM6E"
plink -batch -ssh -hostkey "$HOSTKEY" -pw "$SSH_PASS" getdoday@getdoday.ru "<команда>"
```

**Sudo нет** — это FastPanel-managed, можно только пользовательские операции.
Nginx-конфиг изменить нельзя без сообщения юзеру.

### 🟢 Smoke-команды

```bash
# Health
for p in /health /health/deep /lessio /lessio/help /lessio/blog /u/demo; do
  printf "%-20s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "https://getdoday.ru$p"
done

# Прод SHA
curl -s https://getdoday.ru/version

# Bot жив?
LESSIO_TOKEN=$(grep '^LESSIO_BOT_TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
curl -s "https://api.telegram.org/bot${LESSIO_TOKEN}/getMe"
```

## 6. Workflow rules (важно соблюдать)

### Stylistic

- **Commits:** russian past-tense, краткие. Multiline body OK для контекста.
  Пример: `fix(bot): custom httpcore backend для обхода DNS-блока`.
- **Per-feature folders:** не `models/`, `routes/`, `services/` — а
  `app/feature_name/{models,router,service}.py`. Так уже устроено для
  `auth`, `tasks`, `lessio`, etc.
- **Russian commit + English code/docs.** Никогда не писать русский в
  identifiers/comments кода (ruff RUF001/002/003 будет ругаться — добавь
  per-file-ignore в `pyproject.toml` если действительно нужно).

### Code quality bar

- **Pre-commit hooks обязательны** (ruff format + check + mypy --strict +
  lint_templates). Никогда не push'ь с `--no-verify`.
- **Тесты обязательны** для нового feature. Минимум — happy-path test +
  edge-case test. Используй `superpowers:test-driven-development` если
  применимо.
- **Verification before completion** (см. skill `superpowers:verification-before-completion`):
  smoke на проде после deploy, не «push'нул и забыл».

### Branching

- Работа сразу на `master`. Auto-deploy подхватывает.
- Если очень нужна изоляция — `git worktree add` (см. skill
  `superpowers:using-git-worktrees`).

### Скрытые правила (memory)

Все правила также в `C:\Users\Yaroslav\.claude\projects\c--www-Yaroslav-SchoolProject\memory\MEMORY.md`
— это auto-memory, подгружается каждый раз. Если делаешь новый проект и узнаёшь
что-то важное → сохрани в memory (см. skill `auto memory` в системе).

## 7. Anti-patterns (что НЕ делать)

- ❌ **Не дублируй** существующий проект из раздела 3.
- ❌ **Не возвращай в Doday Tasks:** gamification, habits, mood, time-tracking,
  achievements. Это убрано в pivot 2026-05-13 намеренно.
- ❌ **Не используй AI для cheating** (решать домашку за юзера). Doday и его
  суб-проекты помогают **учиться**, не списывать.
- ❌ **Не требуй юр.лица РФ для оплаты.** Stars единственный канал без барьеров.
- ❌ **Не трогай** код Tap Tower (port 8012) и IndigoSmart (port 8000).
- ❌ **Не создавай** local PostgreSQL. Используй managed remote через `.env`.
- ❌ **Не push'ай** `.env` или секреты (gitignored, проверь перед `git add`).
- ❌ **Не делай destructive ops** (`git push --force`, `reset --hard`,
  `rm -rf /var/www/...`) без явного запроса юзера.
- ❌ **Не пиши в шаблонах** русские identifiers/CSS-классы. Только в content.

## 8. Что есть полезного в monorepo (бери и используй)

### Готовые helper'ы

- `app/auth/deps.py` — `CurrentUser`, `RequiredUser`, `RequiredAdmin`
- `app/auth/rate_limit.py` — sliding-window rate limiter
- `app/billing/stars.py` — Stars-payment payload signing/validating
- `app/telegram/bot.py` — bot worker boilerplate с network workaround
- `app/lessio/email.py` — пример send_*_email с Jinja-template'ами
- `app/lessio/cron.py` — пример batch-jobs (reminders, digests, audits)
- `app/lessio/og_image.py` — серверная генерация OG-image SVG

### Готовые UI-паттерны (Jinja templates)

- `lessio/_logo.html` — единый партиал лого (3 размера)
- `lessio/_base_marketing.html` — публичный layout с header/footer
- `lessio/_base_auth.html` — auth-pages (login/register/setup-profile)
- `lessio/app/_base.html` — cabinet shell с sidebar + mobile drawer
- `lessio/404.html` — branded 404 с search-input по контенту

### Готовая инфраструктура

- Sitemap auto-builder в `app/main.py` (`/sitemap.xml`)
- Robots.txt с per-route allow/disallow
- Custom 404 middleware (path-based template selection)
- Sentry integration через `_init_sentry`
- Yandex Metrika через `request.state.ya_metrika_id`
- IndexNow ping для Yandex/Bing (`app/lessio/indexnow.py`)

## 9. Инструкции тебе, следующий Opus

1. **Прочти весь этот файл целиком.** Не скип.

2. **Спроси юзера** что он хочет сделать. Если он сказал «придумай проект» —
   предложи 2-3 варианта из раздела 3 («Идеи»). Не бери из списка
   «Существующих проектов».

3. **Используй superpowers skills** (доступны через `Skill` tool):
   - `brainstorming` — для дизайна нового проекта
   - `writing-plans` — для разбивки на чанки
   - `executing-plans` — для последовательной реализации
   - `systematic-debugging` — когда что-то ломается
   - `test-driven-development` — для критичной логики
   - `using-git-worktrees` — для изоляции

   Юзер дал full autonomy («сам всё реши»), так что **skip user-approval gates**
   где это безопасно — но **не** скипай тесты, verification, security.

4. **Соблюдай раздел 6** (workflow rules) — особенно commits + tests.

5. **Используй раздел 8** — не пиши заново то что уже есть.

6. **Когда закончил/довёл до production** — обнови этот файл:
   ```markdown
   ## 3. Существующие проекты
   ...
   | **<Твой-Проект>** | `getdoday.ru/<path>` | `@<bot>` или `—` | <status> | <одна-строка-описания> |
   ```
   + при необходимости добавь подсекцию с подробностями ниже таблицы.

7. **Не ломай** существующие проекты. Все 234 lessio-тестов и 850+ doday-тестов
   должны оставаться зелёные после твоих изменений.

8. **Не используй** этот файл для дампа всего что ты узнал — он должен
   оставаться **читаемым за 10 минут**. Подробности — в `PROGRESS.md` (там
   мы пишем хронологию сессий).

## 10. Дополнительные файлы для контекста

Если нужно глубже:

- `PROGRESS.md` — хронология сессий, что когда делалось
- `docs/superpowers/specs/*.md` — design-specs прошлых features
- `docs/superpowers/plans/*.md` — implementation plans прошлых features
- `docs/YOUR-LAUNCH-PLAN.md` — Lessio prod-launch checklist для юзера
- `docs/lessio-production-launch.md` — технические launch-details
- `CLAUDE.md` (если есть) — project-level instructions

## 11. Связь с юзером

- **В чате:** русский, краткие end-of-turn summaries (1-2 предложения).
- **Tone:** прямой, без воды. Юзер не любит «I'll continue to» — просто
  делай.
- **Когда задаёшь вопрос:** реальный выбор, не риторический. Если можно
  решить сам — решай.
- **Не оффери `/schedule`** без конкретной даты-обязательства в работе.

---

> _Этот файл — живой документ. Обновляй раздел 3 после каждого нового
> проекта. Если нашёл новую gotcha — добавь в раздел 5. Не разрастай
> файл бесконечно: ужимай старые секции если новые требуют места._
