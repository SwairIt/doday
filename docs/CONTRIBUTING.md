# Contributing to Doday

Это короткая шпаргалка для тех, кто работает над репозиторием — как клонировать, как добавить фичу, как деплоить.

## Старт

```bash
git clone https://github.com/SwairIt/SchoolProject.git
cd SchoolProject
uv sync --all-groups          # ставит app + dev зависимости
cp .env.example .env          # редактируй: DATABASE_URL, APP_SECRET_KEY и т.д.
uv run alembic upgrade head   # миграции на твоей локальной БД
uv run pre-commit install     # включает pre-commit hooks (один раз)
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Открой `http://127.0.0.1:8000` — должна показаться лендинг-страница.

## Перед коммитом

Pre-commit запустится автоматически на `git commit`. Он гоняет:

- `ruff format` — формат
- `ruff check` — линт
- `mypy --strict` — типы
- `scripts/lint_templates.py` — шаблонные правила (`|tojson|safe` в атрибутах и т.д.)

Если что-то падает — фикси и коммить заново. Никогда не используй `--no-verify`, кроме экстренных случаев.

Pytest в pre-commit **не** входит (310+ тестов = слишком долго). Гонять надо вручную:
```bash
uv run pytest -q                          # все тесты
uv run pytest tests/test_<feature>.py -v  # точечно
```

## Структура

```
app/<feature>/
  __init__.py
  router.py      # FastAPI endpoints
  service.py     # бизнес-логика (чистые async-функции, принимают AsyncSession)
  models.py      # SQLAlchemy ORM-модели
  schemas.py     # Pydantic v2 модели для I/O
  templates_data.py  # (опционально) встроенные данные (шаблоны проектов и т.п.)

app/templates/         # Jinja2 шаблоны
  base.html            # лендинг + auth shell
  app_base.html        # /app/* shell с sidebar + topbar
  _partials/           # переиспользуемые куски (task_row, modal'ы, и т.д.)
  app/<page>.html      # /app/<page> страницы
  auth/<page>.html     # /auth/<page> страницы

tests/                 # pytest файлы — один на feature
  conftest.py          # общие фикстуры; TRUNCATE между функциями

scripts/               # локальные утилиты (линтер, smoke-тест)
docs/                  # CONTRIBUTING + recipes
docs/superpowers/      # специи + планы
alembic/               # миграции БД
deploy/                # nginx, systemd, скрипты деплоя
```

## Как сделать N

См. `docs/recipes/`:

- [add-feature.md](recipes/add-feature.md) — добавить новую фичу с router/service/models/schemas/tests
- [add-migration.md](recipes/add-migration.md) — Alembic-миграция
- [add-template.md](recipes/add-template.md) — Jinja-шаблон без типичных багов
- [add-test.md](recipes/add-test.md) — паттерны тестирования

## Деплой

Прод — Yesbeat hosting, uvicorn на `127.0.0.1:8011`, FastPanel reverse-proxy за nginx + Let's Encrypt.

```bash
python .tmp_ssh_inspect.py    # git pull + clear pyc + restart uvicorn + smoke-test
```

После redeploy скрипт сам проверяет 18 ключевых endpoint'ов через `scripts/smoke_test.py`. Если что-то 404/5xx — падает с понятным выводом.

## Качество

- Ruff правила: `E, F, I, UP, B, S, A, RUF` (см. `pyproject.toml`)
- Mypy `--strict`, без `# type: ignore` без комментария-объяснения
- Pydantic v2 для всего, что пересекает границу
- Pytest-asyncio mode=auto, TRUNCATE между функциями (см. `tests/conftest.py`)

## Git

- Коммиты в master напрямую, без фича-бранчей (один разработчик пока)
- Сообщения коммитов на русском, прошедшее время («добавил X», «исправил Y»)
- Email коммита: `112168281+SwairIt@users.noreply.github.com`
- PAT в `.env` как `TOKEN`, для пушей через одноразовый URL (см. CLAUDE.md)
