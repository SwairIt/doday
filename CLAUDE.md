# CLAUDE.md — как запускать Doday (getdoday.ru)

> Записано 2026-08-24 после того, как «потерялся» проект. Здесь ответ на вопрос
> «где это лежит и как поднять».

## Где что находится

| Что | Где |
|---|---|
| Код сайта (монорепо всех вертикалей) | `D:\New folder (10)\SchoolProject` — **это и есть getdoday.ru** |
| Старый путь | `C:\www-Yaroslav\SchoolProject` — **пусто**, проект переехал на `D:` |
| Игра Doday Arena | `app/static/arena/`, роут `/arena/` |
| «Беллстрой ТВ» | `app/static/game/`, роут `/game/` — другая игра, не трогать |
| Прод-сервер | `192.168.33.3` — **FastPanel**, туда же ведёт запись в `hosts` для `getdoday.ru` |

Внимание: в `C:\Windows\System32\drivers\etc\hosts` прописано
`192.168.33.3 getdoday.ru`. Поэтому домен с этой машины **не идёт в интернет**
(DNS отдаёт 79.137.237.2), а упирается в сервер в локальной сети.

## Локальный запуск (работает без сервера)

```bash
cd "D:/New folder (10)/SchoolProject"
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Открывать: <http://127.0.0.1:8011/> — хаб, <http://127.0.0.1:8011/arena/> — игра.

Три грабли, на которые я уже наступил:

1. **`uv run uvicorn` НЕ работает** — лаунчеры в `.venv` прописаны на путь другой
   машины (`C:\www-Yaroslav\...`) и падают с `uv trampoline failed to canonicalize
   script path`. Та же беда у `pre-commit` и `mypy`. Обход — запускать модулем:
   `uv run python -m uvicorn`, `uv run python -m mypy`, `uv run python -m ruff`.
2. **Порт 8000 занимать нельзя** — там IndigoSmart (в READ-FIRST помечен «не трогать»).
   Порт 8012 — Tap Tower. Свободный для Doday локально: **8011** (он же прод-порт).
3. **Без Postgres поднимутся только хаб и игра.** Разделы Задачи, Q&A, ПДД, Lessio
   отдают 500: в `.env` указан `postgresql+asyncpg://...@localhost:5432/schooltodo`,
   а на машине нет ни службы PostgreSQL, ни Docker. Игра — чистая статика, ей БД не нужна.

Если `.venv` сломан (`ModuleNotFoundError: No module named '_cffi_backend'`):

```bash
uv pip install --reinstall cffi argon2-cffi-bindings
```

## Прод

Из `docs/CONTRIBUTING.md`: хостинг Yesbeat, **uvicorn на `127.0.0.1:8011`**,
FastPanel как reverse-proxy за nginx + Let's Encrypt.

Состояние на 2026-08-24: `https://getdoday.ru/` отдаёт **502** — nginx жив,
бэкенд на сервере не запущен. Панель FastPanel доступна на <http://192.168.33.3/>.

Доступ по SSH описан в `docs/YOUR-LAUNCH-PLAN.md`:

```bash
plink -batch -ssh -hostkey "SHA256:NwU1dGS29JAjs2K5LfEtu3DLFgg04yo7ZEA4iOGkM6E" \
      -pw "$SSH_PASS" getdoday@getdoday.ru "systemctl status doday"
```

**Пароль из `.env` (`SSH_PASS`) сервером отклоняется** — `Access denied`.
Чтобы поднять прод, нужен актуальный пароль или ключ, либо вход в FastPanel.

Локально подменить домен на себя нельзя: правка `hosts` требует прав администратора,
а порт 80 занят системным процессом (PID 4).

## Деплой

Одной командой НА СЕРВЕРЕ из каталога проекта:

```bash
bash scripts/deploy.sh
```

Скрипт: git pull → зависимости → `alembic upgrade head` → перезапуск сервиса →
проверка четырёх ключевых адресов. Любой шаг упал — останавливается, чтобы не
оставить прод в половинчатом состоянии.

`deploy/` содержит `doday.service`, `doday-bot.service`, `nginx.conf`.
Более полная проверка — `scripts/smoke_test.py` (18 endpoint'ов).

## Домены

| Адрес | Что отдаёт |
|---|---|
| `getdoday.ru/` | лендинг Doday Tasks |
| `getdoday.ru/app/today` | само приложение (раньше было `/doday/app/today`) |
| `all.getdoday.ru/` | витрина всех продуктов студии (она же `/all`) |

Поддомен работает через host-rewrite в `app/main.py`, поэтому nginx ОБЯЗАН
передавать `proxy_set_header Host $host;` — иначе на поддомене откроется
лендинг вместо витрины.

Старые адреса `/doday/*` отдают 301 на новые.

## GitHub: репозиторий и токен

Репозиторий называется **`SwairIt/doday`** — так было всегда. Старое имя
`SwairIt/SchoolProject` осталось только в редиректе GitHub и в паре строк
внутри проекта; `origin` указывает на `doday`.

Токен для GitHub API и пуша брать самому из `C:\Users\Yaroslav\.git-credentials`.
Там несколько строк — нужна **именно строка с пользователем `SwairIt`**
(строки с `djdes` — другой аккаунт, у него нет прав на этот репозиторий и
пуш вернёт `403 Permission denied`).

```bash
T=$(awk -F'[/:@]' '$4=="SwairIt"{print $5; exit}' /c/Users/Yaroslav/.git-credentials)
curl -s -H "Authorization: Bearer $T" https://api.github.com/repos/SwairIt/doday/actions/runs?per_page=1
```

Порядок строк в файле важен: git с `credential.helper=store` берёт первую
подходящую по хосту, поэтому строка `SwairIt` должна лежать первой. Токен
никогда не печатать в вывод и не коммитить — только подставлять в переменную.

Логи упавшего прогона CI:

```bash
JID=$(curl -s -H "Authorization: Bearer $T" \
  "https://api.github.com/repos/SwairIt/doday/actions/runs/<RUN_ID>/jobs" \
  | python -c "import json,sys; print(json.load(sys.stdin)['jobs'][0]['id'])")
curl -s -L -H "Authorization: Bearer $T" \
  "https://api.github.com/repos/SwairIt/doday/actions/jobs/$JID/logs" -o ci.log
grep -aE "FAILED tests|failed," ci.log
```

## Проверки перед коммитом

```bash
uv run python -m ruff check . && uv run python -m ruff format --check .
uv run python -m mypy --strict <изменённые файлы>
```

Хук `pre-commit` в этом окружении не запускается (см. грабли №1) — гоняй проверки
руками и указывай это в сообщении коммита, если коммитишь с `--no-verify`.
