"""Build an iCalendar feed of every dated task across the user's account.

Re-uses the same RFC 5545 helpers as the per-project export. Tasks without
a due_at are skipped (calendars need timestamps). Long-lived URL because
calendar apps poll it every 15-60 minutes — caller adds a per-user token
in the URL so it isn't guessable.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project
from app.projects.service import _ics_escape, _ics_fold
from app.tasks.models import Task


async def export_all_to_ics(session: AsyncSession, user_id: UUID) -> str:
    project_rows = await session.execute(select(Project).where(Project.user_id == user_id))
    project_names: dict[UUID, str] = {p.id: p.name for p in project_rows.scalars().all()}

    tasks = (
        (
            await session.execute(
                select(Task).where(Task.user_id == user_id, Task.due_at.is_not(None))
            )
        )
        .scalars()
        .all()
    )

    now_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Doday//Account Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Doday — все задачи",
        "X-PUBLISHED-TTL:PT30M",
    ]
    for t in tasks:
        if t.due_at is None:
            continue
        project_name = project_names.get(t.project_id, "")
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{t.id}@doday.app")
        lines.append(f"DTSTAMP:{now_stamp}")
        if t.due_date_only:
            d = t.due_at.date().strftime("%Y%m%d")
            lines.append(f"DTSTART;VALUE=DATE:{d}")
        else:
            lines.append(f"DTSTART:{t.due_at.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}")
        prio_prefix = "" if t.priority.value == "p4" else f"[!{t.priority.value[1:]}] "
        done_prefix = "[✓] " if t.is_completed else ""
        lines.append(f"SUMMARY:{_ics_escape(done_prefix + prio_prefix + t.title)}")
        if project_name:
            lines.append(f"CATEGORIES:{_ics_escape(project_name)}")
        if t.description:
            lines.append(f"DESCRIPTION:{_ics_escape(t.description)}")
        lines.append("STATUS:COMPLETED" if t.is_completed else "STATUS:CONFIRMED")
        if t.recurrence:
            freq_map = {
                "daily": "DAILY",
                "weekly": "WEEKLY",
                "monthly": "MONTHLY",
                "yearly": "YEARLY",
            }
            freq = freq_map.get(t.recurrence)
            if freq:
                lines.append(f"RRULE:FREQ={freq}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"
