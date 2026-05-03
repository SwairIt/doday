"""Comment service — CRUD with task-ownership checks."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.models import Comment
from app.tasks.service import get_task


class CommentNotFound(Exception):
    """Comment does not exist or does not belong to the requesting user."""


async def list_comments(session: AsyncSession, user_id: UUID, task_id: UUID) -> list[Comment]:
    await get_task(session, user_id, task_id)
    result = await session.execute(
        select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at)
    )
    return list(result.scalars().all())


async def get_comment(session: AsyncSession, user_id: UUID, comment_id: UUID) -> Comment:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.user_id != user_id:
        raise CommentNotFound(str(comment_id))
    return comment


async def create_comment(
    session: AsyncSession, user_id: UUID, *, task_id: UUID, body: str
) -> Comment:
    await get_task(session, user_id, task_id)
    comment = Comment(task_id=task_id, user_id=user_id, body=body)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment


async def update_comment(
    session: AsyncSession, user_id: UUID, comment_id: UUID, *, body: str
) -> Comment:
    comment = await get_comment(session, user_id, comment_id)
    comment.body = body
    await session.commit()
    await session.refresh(comment)
    return comment


async def delete_comment(session: AsyncSession, user_id: UUID, comment_id: UUID) -> None:
    comment = await get_comment(session, user_id, comment_id)
    await session.delete(comment)
    await session.commit()
