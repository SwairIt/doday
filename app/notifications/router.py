"""HTTP-эндпоинты колокольчика: список уведомлений и отметка «прочитано»."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import DbSession, RequiredUser
from app.notifications.service import (
    list_notifications,
    mark_all_read,
    unread_count,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: datetime


class NotificationsResponse(BaseModel):
    unread: int
    items: list[NotificationOut]


@router.get("", response_model=NotificationsResponse)
async def my_notifications(user: RequiredUser, session: DbSession) -> NotificationsResponse:
    """Колокольчик тянет это: количество непрочитанных + последние уведомления."""
    items = await list_notifications(session, user.id, limit=20)
    return NotificationsResponse(
        unread=await unread_count(session, user.id),
        items=[
            NotificationOut(
                id=n.id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                link=n.link,
                read=n.read_at is not None,
                created_at=n.created_at,
            )
            for n in items
        ],
    )


@router.post("/read", status_code=204)
async def mark_read(user: RequiredUser, session: DbSession) -> None:
    """Отмечает все уведомления пользователя прочитанными (при открытии колокольчика)."""
    await mark_all_read(session, user.id)
