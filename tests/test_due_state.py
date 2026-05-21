"""Unit tests for the `due_state` template helper (deadline row colouring)."""

from datetime import UTC, datetime, timedelta

from app.tasks.models import Task
from app.views.template_filters import due_label, due_state


def test_no_due_date() -> None:
    assert due_state(Task(due_at=None, due_date_only=True, is_completed=False)) == "none"


def test_overdue_date_only() -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    assert due_state(Task(due_at=yesterday, due_date_only=True, is_completed=False)) == "overdue"


def test_today_date_only() -> None:
    now = datetime.now(UTC)
    assert due_state(Task(due_at=now, due_date_only=True, is_completed=False)) == "today"


def test_future_date_only() -> None:
    later = datetime.now(UTC) + timedelta(days=2)
    assert due_state(Task(due_at=later, due_date_only=True, is_completed=False)) == "future"


def test_completed_never_overdue() -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    assert due_state(Task(due_at=yesterday, due_date_only=True, is_completed=True)) == "future"


def test_overdue_timed() -> None:
    past = datetime.now(UTC) - timedelta(hours=2)
    assert due_state(Task(due_at=past, due_date_only=False, is_completed=False)) == "overdue"


def test_today_timed_later() -> None:
    # A timed deadline later today still counts as "today".
    soon = datetime.now(UTC) + timedelta(hours=3)
    state = due_state(Task(due_at=soon, due_date_only=False, is_completed=False))
    assert state in {"today", "future"}  # tolerant near midnight rollover


def test_future_timed() -> None:
    later = datetime.now(UTC) + timedelta(days=2)
    assert due_state(Task(due_at=later, due_date_only=False, is_completed=False)) == "future"


def test_due_label_relative_words() -> None:
    now = datetime.now(UTC)
    assert due_label(Task(due_at=now, due_date_only=True, is_completed=False)) == "Сегодня"
    assert (
        due_label(Task(due_at=now + timedelta(days=1), due_date_only=True, is_completed=False))
        == "Завтра"
    )
    assert (
        due_label(Task(due_at=now - timedelta(days=1), due_date_only=True, is_completed=False))
        == "Вчера"
    )


def test_due_label_absolute_and_timed() -> None:
    far = datetime(2030, 12, 15, tzinfo=UTC)
    assert due_label(Task(due_at=far, due_date_only=True, is_completed=False)) == "15.12"
    assert due_label(Task(due_at=far, due_date_only=False, is_completed=False)) == "15.12 00:00"
    assert due_label(Task(due_at=None, due_date_only=True, is_completed=False)) == ""
