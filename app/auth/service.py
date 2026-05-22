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


async def register_user(session: AsyncSession, payload: RegisterIn) -> User:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyExists(payload.email)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
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


_WELCOME_COMMENT = (
    "👋 Это Doday — твой бесплатный туду-лист.\n\n"
    "Я подкинул 5 обучающих задач — закрой их по порядку, и узнаешь все "
    "ключевые фишки за пару минут.\n\n"
    "Когда разберёшься — удали этот Inbox-список и начни добавлять свои "
    "задачи через «+» вверху или горячую клавишу `q`."
)


async def provision_new_user(session: AsyncSession, user: User) -> None:
    """One-time onboarding: ensure Inbox + universal starter tasks.

    Creates 5 educational tasks that teach the user how Doday works. Idempotent.
    Первой задаче ещё прикладывается приветственный комментарий.
    """
    from app.comments.service import create_comment
    from app.projects.service import ensure_inbox
    from app.tasks.service import create_task, list_tasks

    inbox = await ensure_inbox(session, user.id)
    existing = await list_tasks(session, user.id, project_id=inbox.id, include_completed=True)
    if existing:
        return

    samples = _starter_samples()
    first_task_id = None
    for idx, (title, due, prio) in enumerate(samples):
        task = await create_task(
            session,
            user.id,
            project_id=inbox.id,
            title=title,
            due_at=due,
            priority=prio,
        )
        if idx == 0:
            first_task_id = task.id

    if first_task_id is not None:
        await create_comment(
            session,
            user.id,
            task_id=first_task_id,
            body=_WELCOME_COMMENT,
        )


def _starter_samples() -> list[tuple[str, datetime | None, TaskPriority]]:
    """5 educational starter tasks — teach the user how Doday works.

    Tasks go from simplest (tick the checkbox) to advanced (filters, projects).
    Дедлайны сегодня/завтра/через 3 дня — чтобы пользователь увидел задачи
    и в /app/today, и в /app/upcoming, и понял разницу.
    """
    from datetime import timedelta

    today = datetime.now(UTC).replace(hour=23, minute=59, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    in_three_days = today + timedelta(days=3)

    return [
        # 1. Самое простое действие — обучает, как закрыть задачу.
        (
            "✅ Кликни кружок слева, чтобы закрыть задачу — попробуй на этой",
            today,
            TaskPriority.P1,
        ),
        # 2. Создание задачи — учит главному действию приложения.
        (
            "➕ Нажми «+» вверху или клавишу `q` — создай свою первую задачу",
            today,
            TaskPriority.P2,
        ),
        # 3. Естественные даты — киллер-фича quick-add.
        (
            "📅 Попробуй: добавь задачу с текстом «купить хлеб завтра» — поймёт "
            "слово «завтра» как дедлайн",
            tomorrow,
            TaskPriority.P3,
        ),
        # 4. Поиск/командное меню — наша Cmd-K.
        (
            "🔍 Жми ⌘K (или Ctrl+K) — откроется поиск + быстрые команды по всему приложению",
            tomorrow,
            TaskPriority.P3,
        ),
        # 5. Статистика — полезная фича для всех.
        (
            "📊 Статистика: посмотри на /app/stats — давай увидим прогресс после нескольких задач",
            in_three_days,
            TaskPriority.P4,
        ),
    ]


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    normalized = email.lower().strip()
    result = await session.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    # Email verification is "soft": unverified users may sign in and use the app.
    # Verification only gates email-dependent features (digest / password reset).
    return user
