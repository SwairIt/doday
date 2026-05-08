# Recipe: добавить миграцию БД

## Создать ревизию

```bash
uv run alembic revision --autogenerate -m "<feature>: <что-делает>"
```

Пример сообщения: `"notes: add archived flag column"`.

Файл создаётся в `alembic/versions/<hash>_<message>.py`.

## Проверить SQL

`alembic --autogenerate` НЕ всегда правильно угадывает изменения. Открой файл и убедись:

- `op.create_table` — все нужные столбцы, типы, FK, индексы есть
- `op.alter_column` — `nullable` правильное (если меняешь existing column на NOT NULL — нужен default или backfill)
- Индексы создаются после столбцов, не до
- ENUM-типы создаются явно (`postgresql.ENUM(...).create(op.get_bind())`)

Если автоген сгенерировал что-то не то — отредактируй вручную, это нормально.

## Применить локально

```bash
uv run alembic upgrade head
```

Если падает — фикси миграцию или модель.

## Проверить reversibility

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Если `downgrade` падает — допиши `op.drop_table` / `op.drop_column` руками в `def downgrade()`.

## Backfill данных

Если миграция требует backfill (например, заполнить новый NOT NULL столбец на существующих строках), используй чистый SQL внутри `def upgrade()`:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE users SET trial_ends_at = NOW() + INTERVAL '14 days' WHERE trial_ends_at IS NULL")
    op.alter_column("users", "trial_ends_at", nullable=False)
```

## Прод-деплой

После пуша на master, на сервере:
```bash
ssh getdoday@getdoday.ru
cd /var/www/getdoday/data/www/getdoday.ru/app
uv run alembic upgrade head
```

(Или встроить в `.tmp_ssh_inspect.py` — но обычно миграции редкие, проще руками.)

## Откат на проде если миграция сломала

```bash
uv run alembic downgrade -1
git revert HEAD     # откатить код-коммит
git push ...
python .tmp_ssh_inspect.py    # redeploy откаченного кода
```

## Анти-паттерны

- ❌ Не редактировать уже применённую миграцию (если она в master + на проде) — делай новую
- ❌ Не использовать `import` приложения внутри миграции (модели могут поменяться, миграция должна быть статичной)
- ❌ Не делать `DROP TABLE` без бэкапа БД сначала
