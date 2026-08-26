"""Логика чата: история, суточные лимиты, сборка контекста для модели."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import Message
from app.ai.models import AiMessage, AiUsageDaily
from app.tasks.models import Task

# Сколько запросов к модели можно сделать за сутки. Ключ пользовательский,
# платит он же — ограничение нужно не ради денег, а чтобы случайный цикл в
# скрипте не выжег чужой баланс за ночь.
DAILY_LIMIT = 50

# Сколько прошлых сообщений отдаём модели. Больше — дороже и медленнее, а
# школьный вопрос редко требует длинной предыстории.
HISTORY_DEPTH = 20

MAX_PROMPT_CHARS = 4000

SYSTEM_PROMPT = (
    "Ты помощник в приложении Doday — планировщике для школьников и студентов. "
    "Отвечай по-русски, коротко и по делу, обращайся на «ты». "
    "Если объясняешь — объясняй так, чтобы понял школьник: простыми словами, "
    "с примерами. Если в вопросе есть ошибка или подвох — скажи об этом. "
    "Не выдумывай факты: если чего-то не знаешь, так и напиши."
)


class LimitReached(Exception):
    """Суточный лимит запросов исчерпан."""

    def __init__(self, used: int, limit: int) -> None:
        super().__init__(f"израсходовано {used} из {limit}")
        self.used = used
        self.limit = limit


class PromptTooLong(Exception):
    """Вопрос длиннее, чем мы готовы отправить."""


async def usage_today(session: AsyncSession, user_id: UUID) -> int:
    """Сколько запросов пользователь уже сделал сегодня."""
    today = datetime.now(UTC).date()
    result = await session.execute(
        select(AiUsageDaily.requests).where(
            AiUsageDaily.user_id == user_id, AiUsageDaily.day == today
        )
    )
    return result.scalar_one_or_none() or 0


async def check_and_count(session: AsyncSession, user_id: UUID) -> int:
    """Проверить лимит и сразу занять один запрос.

    Инкремент атомарный (INSERT ... ON CONFLICT DO UPDATE) — параллельные
    вкладки не смогут проскочить лимит вдвоём. Возвращает новое значение.
    """
    today: date = datetime.now(UTC).date()
    used = await usage_today(session, user_id)
    if used >= DAILY_LIMIT:
        raise LimitReached(used, DAILY_LIMIT)

    stmt = (
        pg_insert(AiUsageDaily)
        .values(user_id=user_id, day=today, requests=1)
        .on_conflict_do_update(
            index_elements=[AiUsageDaily.user_id, AiUsageDaily.day],
            set_={"requests": AiUsageDaily.requests + 1},
        )
        .returning(AiUsageDaily.requests)
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(result.scalar_one())


async def history(
    session: AsyncSession, user_id: UUID, task_id: UUID | None, limit: int = HISTORY_DEPTH
) -> list[AiMessage]:
    """Последние сообщения диалога в хронологическом порядке."""
    stmt = select(AiMessage).where(AiMessage.user_id == user_id)
    stmt = (
        stmt.where(AiMessage.task_id == task_id)
        if task_id
        else stmt.where(AiMessage.task_id.is_(None))
    )
    stmt = stmt.order_by(AiMessage.created_at.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    return list(reversed(rows))


async def save_message(
    session: AsyncSession,
    user_id: UUID,
    *,
    role: str,
    content: str,
    task_id: UUID | None = None,
) -> AiMessage:
    message = AiMessage(user_id=user_id, task_id=task_id, role=role, content=content)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def clear_thread(session: AsyncSession, user_id: UUID, task_id: UUID | None) -> int:
    """Удалить переписку. Возвращает число удалённых сообщений."""
    rows = await history(session, user_id, task_id, limit=10_000)
    for row in rows:
        await session.delete(row)
    await session.commit()
    return len(rows)


async def task_context(session: AsyncSession, user_id: UUID, task_id: UUID) -> str | None:
    """Описание задачи для подстановки в разговор.

    Чтобы школьнику не приходилось пересказывать условие: название, описание
    и срок уходят модели автоматически.
    """
    task = (
        await session.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    ).scalar_one_or_none()
    if task is None:
        return None
    parts = [f"Задача: {task.title}"]
    if task.description:
        parts.append(f"Подробности: {task.description}")
    if task.due_at:
        parts.append(f"Сдать до: {task.due_at:%d.%m.%Y}")
    return "\n".join(parts)


def build_messages(prompt: str, past: list[AiMessage], context: str | None = None) -> list[Message]:
    """Собрать запрос к модели: системная часть, контекст, история, вопрос."""
    if len(prompt) > MAX_PROMPT_CHARS:
        raise PromptTooLong(f"вопрос длиннее {MAX_PROMPT_CHARS} символов")

    system = SYSTEM_PROMPT
    if context:
        system = f"{system}\n\nПользователь спрашивает в контексте своей задачи.\n{context}"

    messages: list[Message] = [{"role": "system", "content": system}]
    messages.extend({"role": m.role, "content": m.content} for m in past)
    messages.append({"role": "user", "content": prompt})
    return messages


async def messages_count(session: AsyncSession, user_id: UUID) -> int:
    """Сколько всего сообщений у пользователя — для статистики и тестов."""
    result = await session.execute(
        select(func.count()).select_from(AiMessage).where(AiMessage.user_id == user_id)
    )
    return int(result.scalar_one())
