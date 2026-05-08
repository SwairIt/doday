# Recipe: добавить новую фичу

Допустим, нужна фича `notes` — заметки, не привязанные к задачам. Шаги:

## 1. Создать пакет фичи

```
app/notes/
  __init__.py
  models.py
  schemas.py
  service.py
  router.py
```

`app/notes/__init__.py`:
```python
"""Notes feature — standalone notes, no task-linkage."""
```

`app/notes/models.py`:
```python
"""SQLAlchemy ORM model for notes."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`app/notes/schemas.py`:
```python
"""Pydantic schemas for notes I/O."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class NoteOut(BaseModel):
    id: UUID
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

`app/notes/service.py`:
```python
"""Business logic for notes — pure async functions, no FastAPI deps."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notes.models import Note


class NoteNotFound(Exception):
    """Raised when looking up a note that doesn't exist or isn't owned by user."""


async def list_notes(session: AsyncSession, user_id: UUID) -> list[Note]:
    result = await session.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_note(
    session: AsyncSession, user_id: UUID, *, title: str, body: str
) -> Note:
    note = Note(user_id=user_id, title=title, body=body)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def get_note(session: AsyncSession, user_id: UUID, note_id: UUID) -> Note:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise NoteNotFound(str(note_id))
    return note
```

`app/notes/router.py`:
```python
"""Notes HTTP endpoints — JSON CRUD."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.notes.schemas import NoteCreate, NoteOut, NoteUpdate
from app.notes.service import NoteNotFound, create_note, get_note, list_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
async def list_endpoint(user: RequiredUser, session: DbSession) -> list[NoteOut]:
    notes = await list_notes(session, user.id)
    return [NoteOut.model_validate(n) for n in notes]


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: NoteCreate, user: RequiredUser, session: DbSession
) -> NoteOut:
    note = await create_note(session, user.id, title=payload.title, body=payload.body)
    return NoteOut.model_validate(note)


@router.get("/{note_id}", response_model=NoteOut)
async def get_endpoint(
    note_id: UUID, user: RequiredUser, session: DbSession
) -> NoteOut:
    try:
        note = await get_note(session, user.id, note_id)
    except NoteNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "заметка не найдена") from e
    return NoteOut.model_validate(note)
```

## 2. Зарегистрировать router

В `app/main.py`, рядом с другими `include_router(...)`, добавь:
```python
from app.notes.router import router as notes_router
# ...
app.include_router(notes_router)
```

## 3. Создать миграцию

```bash
uv run alembic revision --autogenerate -m "notes: initial table"
```

Откроется файл `alembic/versions/<hash>_notes_initial_table.py`. Проверь:
- `op.create_table('notes', ...)` — присутствует
- ForeignKey на `users.id` с `ondelete='CASCADE'`
- Индекс на `user_id`

Применить локально:
```bash
uv run alembic upgrade head
```

Проверить reversibility:
```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

## 4. Написать тесты

См. [add-test.md](add-test.md) для паттернов. Минимум — `tests/test_notes.py` с 4 тестами:

```python
"""Tests for app/notes/."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_note_returns_201_with_payload(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post("/api/notes", json={"title": "first", "body": "hello"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "first"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_notes_returns_users_own_notes(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/notes", json={"title": "n1", "body": ""})
    await auth_client.post("/api/notes", json={"title": "n2", "body": ""})
    resp = await auth_client.get("/api/notes")
    assert resp.status_code == 200
    titles = {n["title"] for n in resp.json()}
    assert titles == {"n1", "n2"}


@pytest.mark.asyncio
async def test_get_other_users_note_returns_404(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    created = await auth_client.post("/api/notes", json={"title": "private", "body": ""})
    note_id = created.json()["id"]
    resp = await second_auth_client.get(f"/api/notes/{note_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/notes")
    assert resp.status_code == 401
```

(Фикстуры `auth_client`, `second_auth_client`, `client` уже определены в `tests/conftest.py`.)

## 5. Прогон

```bash
uv run pytest tests/test_notes.py -v
uv run mypy --strict app/notes/
uv run ruff check app/notes/ tests/test_notes.py
```

Все три должны быть зелёными.

## 6. Smoke-тест на проде после деплоя

Если у фичи есть публичный URL — добавь в `scripts/smoke_test.py` в `ENDPOINTS`:
```python
Endpoint("/api/notes", 401, "auth-gate-notes"),
```

(401 потому что без токена.) Чтобы знать что роут зарегистрирован после redeploy.

## 7. Коммит

```bash
git add app/notes/ tests/test_notes.py alembic/versions/<hash>*.py
# (если поменял scripts/smoke_test.py — добавь и его)
git commit -m "feat: notes — стандалон-заметки + CRUD-эндпоинты + миграция"
```
