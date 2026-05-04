"""Auth business logic — registration, email verification, authentication."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.security import hash_password, verify_password
from app.tasks.models import TaskPriority


class EmailAlreadyExists(Exception):
    """Raised when attempting to register an email that's already taken."""


class TokenInvalid(Exception):
    """User ID from a verification token is malformed or unknown."""


class InvalidCredentials(Exception):
    """Wrong email or password during login."""


class EmailNotVerified(Exception):
    """Login attempted but the email hasn't been verified yet."""


async def register_user(session: AsyncSession, payload: RegisterIn) -> User:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyExists(payload.email)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        audience=payload.audience,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def mark_email_verified(session: AsyncSession, user_id: str) -> User:
    try:
        uid = UUID(user_id)
    except ValueError as e:
        raise TokenInvalid("malformed user id") from e

    user = await session.get(User, uid)
    if user is None:
        raise TokenInvalid("user not found")

    was_unverified = user.email_verified_at is None
    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)

    if was_unverified:
        await provision_new_user(session, user)

    return user


async def provision_new_user(session: AsyncSession, user: User) -> None:
    """One-time onboarding: ensure Inbox + audience-specific starter tasks.

    Sample set is picked by `user.audience` so a schoolchild, an office worker
    and a "for me" user each see relevant first impressions. Idempotent.
    """
    from app.projects.service import ensure_inbox
    from app.tasks.service import create_task, list_tasks

    inbox = await ensure_inbox(session, user.id)
    existing = await list_tasks(session, user.id, project_id=inbox.id, include_completed=True)
    if existing:
        return

    samples = _starter_samples_for(user.audience)
    for title, due, prio in samples:
        await create_task(
            session,
            user.id,
            project_id=inbox.id,
            title=title,
            due_at=due,
            priority=prio,
        )


def _starter_samples_for(
    audience: str | None,
) -> list[tuple[str, datetime | None, TaskPriority]]:
    """Pick the right onboarding sample set for the chosen audience."""
    from datetime import timedelta

    today = datetime.now(UTC).replace(hour=23, minute=59, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    in_three_days = today + timedelta(days=3)

    if audience == "school":
        return [
            ("📚 Сделать домашку на завтра", today, TaskPriority.P1),
            ("📝 Подготовиться к контрольной", tomorrow, TaskPriority.P2),
            ("🎒 Собрать рюкзак вечером", today, TaskPriority.P3),
            ("📖 Прочитать главу по литературе", in_three_days, TaskPriority.P3),
            ("💡 Совет: ⌘K (или Ctrl+K) — быстрый поиск по задачам", None, TaskPriority.P4),
        ]
    if audience == "company":
        return [
            ("☕ Утренний стендап в 10:00", today, TaskPriority.P2),
            ("📊 Подготовить статус-репорт", today, TaskPriority.P1),
            ("🤝 1:1 встреча с тимлидом", tomorrow, TaskPriority.P2),
            ("🚀 Закрыть тикет из спринта", in_three_days, TaskPriority.P3),
            ("💡 Совет: shift+пробел — добавить задачу из любого экрана", None, TaskPriority.P4),
        ]
    if audience == "personal":
        return [
            ("🌱 Выпить стакан воды — простой первый чек-ин", today, TaskPriority.P3),
            ("🛒 Купить продукты на неделю", today, TaskPriority.P2),
            ("📞 Позвонить близкому человеку", tomorrow, TaskPriority.P3),
            ("📚 30 минут чтения перед сном", in_three_days, TaskPriority.P4),
            ("💡 Совет: жми ⌘K (Ctrl+K) — поиск и быстрые команды", None, TaskPriority.P4),
        ]
    return [
        ("Попробуй закрыть эту задачу — кликни кружок слева", today, TaskPriority.P2),
        ("Создай свою задачу через «+» вверху", today, TaskPriority.P3),
        (
            "Открой задачу мышкой и наведи — появятся кнопки редактировать и удалить",
            tomorrow,
            TaskPriority.P4,
        ),
        ("Нажми ⌘K (или Ctrl+K) — откроется поиск", None, TaskPriority.P4),
    ]


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    normalized = email.lower().strip()
    result = await session.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    if user.email_verified_at is None:
        raise EmailNotVerified()
    return user
