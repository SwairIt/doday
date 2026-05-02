"""Auth business logic — user registration, etc."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import RegisterIn
from app.auth.security import hash_password


class EmailAlreadyExists(Exception):
    """Raised when attempting to register an email that's already taken."""


async def register_user(session: AsyncSession, payload: RegisterIn) -> User:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyExists(payload.email)

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
