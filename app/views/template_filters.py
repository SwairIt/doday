"""Small presentation helpers exposed to Jinja templates.

Registered as Jinja globals on the template environments that render task rows
(`app/views/router.py` and `app/views/htmx.py`). Pure functions, no DB access.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.tasks.models import Task


def due_state(task: Task) -> str:
    """Classify a task's deadline for row styling.

    Returns one of ``"overdue" | "today" | "future" | "none"``. Completed tasks
    never count as overdue/today (their row is already muted), so they fall back
    to ``"future"``. Date-only deadlines compare by calendar day; timed
    deadlines compare against the current instant (UTC).
    """
    due = task.due_at
    if due is None:
        return "none"
    if task.is_completed:
        return "future"
    now = datetime.now(UTC)
    today = now.date()
    if task.due_date_only:
        day = due.date()
        if day < today:
            return "overdue"
        if day == today:
            return "today"
        return "future"
    if due < now:
        return "overdue"
    if due.date() == today:
        return "today"
    return "future"
