"""Tests for Label model and the task_labels association table."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.labels.models import Label, task_labels
from app.projects.models import Project
from app.tasks.models import Task


async def _seed(db_session: AsyncSession) -> tuple[User, Project, Task]:
    u = User(email="l@school.ru", password_hash="argon2-fake")
    db_session.add(u)
    await db_session.commit()
    p = Project(user_id=u.id, name="Inbox", slug="inbox", is_inbox=True)
    db_session.add(p)
    await db_session.commit()
    t = Task(user_id=u.id, project_id=p.id, title="X")
    db_session.add(t)
    await db_session.commit()
    return u, p, t


async def test_label_round_trip(db_session: AsyncSession) -> None:
    u, _, _ = await _seed(db_session)
    label = Label(user_id=u.id, name="Срочно", slug="srochno", color="rose")
    db_session.add(label)
    await db_session.commit()
    await db_session.refresh(label)
    assert label.id is not None


async def test_label_slug_unique_per_user(db_session: AsyncSession) -> None:
    u, _, _ = await _seed(db_session)
    db_session.add(Label(user_id=u.id, name="A", slug="a"))
    await db_session.commit()

    db_session.add(Label(user_id=u.id, name="A again", slug="a"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_task_labels_association(db_session: AsyncSession) -> None:
    u, _, t = await _seed(db_session)
    label = Label(user_id=u.id, name="Дом", slug="dom")
    db_session.add(label)
    await db_session.commit()
    await db_session.refresh(label)

    await db_session.execute(task_labels.insert().values(task_id=t.id, label_id=label.id))
    await db_session.commit()

    rows = (await db_session.execute(task_labels.select())).all()
    assert len(rows) == 1
