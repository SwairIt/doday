"""Service-level tests for labels."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.labels.service import (
    LabelNotFound,
    attach_label,
    create_label,
    delete_label,
    detach_label,
    find_or_create_by_name,
    list_labels,
    list_task_labels,
    update_label,
)
from app.tasks.service import create_task


async def _user(db_session: AsyncSession, email: str = "u@s.ru") -> User:
    u = User(email=email, password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    return u


async def test_create_and_list(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    a = await create_label(db_session, user.id, name="Дом")
    b = await create_label(db_session, user.id, name="Работа", color="rose")

    labels = await list_labels(db_session, user.id)
    assert {lab.id for lab in labels} == {a.id, b.id}


async def test_update_label(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    label = await create_label(db_session, user.id, name="Old")
    updated = await update_label(db_session, user.id, label.id, name="New", color="emerald")
    assert updated.name == "New"
    assert updated.color == "emerald"


async def test_delete_label(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    label = await create_label(db_session, user.id, name="X")
    await delete_label(db_session, user.id, label.id)
    with pytest.raises(LabelNotFound):
        await delete_label(db_session, user.id, label.id)


async def test_find_or_create_is_idempotent(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    first = await find_or_create_by_name(db_session, user.id, "@home")
    second = await find_or_create_by_name(db_session, user.id, "@home")
    assert first.id == second.id


async def test_attach_and_detach(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    task = await create_task(db_session, user.id, title="A")
    label = await create_label(db_session, user.id, name="L")

    await attach_label(db_session, user.id, task.id, label.id)
    attached = await list_task_labels(db_session, user.id, task.id)
    assert [lab.id for lab in attached] == [label.id]

    # second attach is a no-op
    await attach_label(db_session, user.id, task.id, label.id)
    attached2 = await list_task_labels(db_session, user.id, task.id)
    assert len(attached2) == 1

    await detach_label(db_session, user.id, task.id, label.id)
    after = await list_task_labels(db_session, user.id, task.id)
    assert after == []
