"""Auth business logic — registration, email verification, authentication."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.security import hash_password, verify_password


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

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


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
    """One-time onboarding: ensure Inbox project and 3 sample tasks.

    Idempotent — re-runs are a no-op if Inbox already has any tasks.
    """
    # Local import to avoid circular dependencies between auth ↔ projects/tasks
    from app.projects.service import ensure_inbox
    from app.tasks.service import create_task, list_tasks

    inbox = await ensure_inbox(session, user.id)
    existing = await list_tasks(session, user.id, project_id=inbox.id, include_completed=True)
    if existing:
        return

    samples = [
        "Попробуй закрыть эту задачу — кликни кружок слева",
        "Перетащи меня в проект через сайдбар",
        "Создай свою задачу через «+» сверху",
    ]
    for title in samples:
        await create_task(session, user.id, project_id=inbox.id, title=title)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    normalized = email.lower().strip()
    result = await session.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    if user.email_verified_at is None:
        raise EmailNotVerified()
    return user
