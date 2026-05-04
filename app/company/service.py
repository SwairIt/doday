"""Build standup-ready summaries from a user's tasks.

Three buckets that map cleanly to the classic standup format:
- yesterday: tasks completed in the last 24h (UTC midnight to UTC midnight)
- today: tasks scheduled for today that aren't done yet
- blockers: tasks overdue OR P1, still open
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import Task, TaskPriority


async def build_standup_report(
    session: AsyncSession, user_id: UUID
) -> dict[str, list[dict[str, object]]]:
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)

    yesterday_done_q = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            func.date(Task.completed_at) == yesterday,
        )
        .order_by(Task.completed_at.desc())
    )
    today_open_q = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(False),
            Task.due_at.is_not(None),
            func.date(Task.due_at) == today,
        )
        .order_by(Task.priority.asc())
    )
    blockers_q = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(False),
            or_(
                Task.priority == TaskPriority.P1,
                and_(Task.due_at.is_not(None), func.date(Task.due_at) < today),
            ),
        )
        .order_by(Task.priority.asc(), Task.due_at.asc())
    )

    yesterday_done = list((await session.execute(yesterday_done_q)).scalars().all())
    today_open = list((await session.execute(today_open_q)).scalars().all())
    blockers = list((await session.execute(blockers_q)).scalars().all())

    return {
        "yesterday": [_serialize(t) for t in yesterday_done],
        "today": [_serialize(t) for t in today_open],
        "blockers": [_serialize(t) for t in blockers],
    }


def _serialize(t: Task) -> dict[str, object]:
    return {
        "id": str(t.id),
        "title": t.title,
        "priority": t.priority.value,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


def render_markdown(report: dict[str, list[dict[str, object]]]) -> str:
    """Plain-text/markdown standup ready to paste into Slack/Telegram."""
    lines: list[str] = []
    lines.append("*Стендап ✋*")
    lines.append("")
    lines.append("*Вчера:*")
    if report["yesterday"]:
        for t in report["yesterday"]:
            lines.append(f"• {t['title']}")
    else:
        lines.append("• (ничего не закрыл)")
    lines.append("")
    lines.append("*Сегодня:*")
    if report["today"]:
        for t in report["today"]:
            lines.append(f"• {t['title']}")
    else:
        lines.append("• (на сегодня ничего не запланировано)")
    lines.append("")
    lines.append("*Блокеры:*")
    if report["blockers"]:
        for t in report["blockers"]:
            lines.append(f"• {t['title']}")
    else:
        lines.append("• нет")
    return "\n".join(lines)
