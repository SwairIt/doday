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


def due_label(task: Task) -> str:
    """Short, human deadline label for the task-row date chip.

    Yesterday/today/tomorrow get relative words; anything else keeps ``dd.mm``.
    Timed deadlines append ``HH:MM``. Returns "" when there is no due date.
    """
    due = task.due_at
    if due is None:
        return ""
    today = datetime.now(UTC).date()
    day = due.date()
    delta = (day - today).days
    if delta == 0:
        base = "Сегодня"
    elif delta == 1:
        base = "Завтра"
    elif delta == -1:
        base = "Вчера"
    else:
        base = due.strftime("%d.%m")
    if not task.due_date_only:
        base += due.strftime(" %H:%M")
    return base
