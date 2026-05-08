# Recipe: написать тест

## Конвенции

- Один файл на feature: `tests/test_<feature>.py`
- Pytest-asyncio mode=auto → `async def test_x(...)` работает без декоратора
- Между функциями `tests/conftest.py` делает TRUNCATE всех таблиц — каждый тест видит чистую БД
- Используем существующие фикстуры из `conftest.py`: `client`, `auth_client`, `second_auth_client`, `db_session`

## Минимальный тест

```python
"""Tests for app/notes/."""

from httpx import AsyncClient


async def test_create_note_returns_201(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/notes", json={"title": "first", "body": ""})
    assert resp.status_code == 201
    assert resp.json()["title"] == "first"


async def test_list_returns_only_own_notes(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    await auth_client.post("/api/notes", json={"title": "mine", "body": ""})
    await second_auth_client.post("/api/notes", json={"title": "yours", "body": ""})

    mine_resp = await auth_client.get("/api/notes")
    titles = [n["title"] for n in mine_resp.json()]
    assert titles == ["mine"]
```

## Тестирование service-функций напрямую

Если хочется протестить service-слой без HTTP:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.notes.service import create_note, list_notes


async def test_create_note_persists(
    db_session: AsyncSession, test_user: User
) -> None:
    note = await create_note(db_session, test_user.id, title="t", body="b")
    assert note.id is not None
    fetched = await list_notes(db_session, test_user.id)
    assert len(fetched) == 1
    assert fetched[0].title == "t"
```

## Параметризация

Для повторяющихся кейсов с разными входами:

```python
import pytest


@pytest.mark.parametrize(
    "title,expected_status",
    [
        ("normal", 201),
        ("", 422),                    # пустой — Pydantic min_length=1
        ("x" * 201, 422),             # слишком длинный — max_length=200
    ],
)
async def test_title_validation(
    auth_client: AsyncClient, title: str, expected_status: int
) -> None:
    resp = await auth_client.post("/api/notes", json={"title": title, "body": ""})
    assert resp.status_code == expected_status
```

## Проверка состояния через DB напрямую

Иногда нужно проверить что fields в БД соответствуют ожиданию (а не возврат API):

```python
from sqlalchemy import select

from app.notes.models import Note


async def test_create_note_sets_user_id_correctly(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    await auth_client.post("/api/notes", json={"title": "t", "body": ""})
    result = await db_session.execute(select(Note).where(Note.user_id == test_user.id))
    notes = result.scalars().all()
    assert len(notes) == 1
```

## Запуск

```bash
uv run pytest tests/test_notes.py -v       # один файл
uv run pytest tests/test_notes.py::test_create_note_returns_201 -v   # одна функция
uv run pytest -q                           # всё
uv run pytest -q -k "create"               # фильтр по имени
```

## Анти-паттерны

- ❌ Не мокай БД — у нас Postgres-test инстанс, conftest TRUNCATE'ит таблицы между функциями. Mock-БД и реальная Postgres ведут себя по-разному (transactions, FK, ENUMs)
- ❌ Не делай `time.sleep(...)` для ожидания async — пиши `await` правильно
- ❌ Не пиши тест без assert'ов («просто проверить что не падает») — это не тест
- ❌ Не завись от порядка тестов (`test_a` потом `test_b`) — каждый тест должен быть автономен; conftest TRUNCATE гарантирует этим
