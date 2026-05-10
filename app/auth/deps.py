"""FastAPI dependencies for auth — current user, require user."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: DbSession) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        uid = UUID(str(user_id))
    except ValueError:
        return None
    return await session.get(User, uid)


CurrentUser = Annotated[User | None, Depends(get_current_user)]


async def require_user(user: CurrentUser) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "не авторизован")
    return user


RequiredUser = Annotated[User, Depends(require_user)]


async def require_admin(user: RequiredUser) -> User:
    """403 if user.is_admin is False. Used for /app/root and /api/admin/*."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "только для администратора")
    return user


RequiredAdmin = Annotated[User, Depends(require_admin)]
