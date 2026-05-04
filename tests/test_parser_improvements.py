"""Tests for the new natural-language patterns in the quickadd parser."""

from datetime import UTC, datetime, timedelta

from app.quickadd.parser import parse_quick_add
from app.tasks.models import TaskPriority

_NOW = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)  # Mon 2026-05-04 10:00 UTC


def test_word_priority_srochno() -> None:
    p = parse_quick_add("срочно купить молоко", now=_NOW)
    assert p.priority == TaskPriority.P1
    assert "молоко" in p.title
    assert "срочно" not in p.title.lower()


def test_word_priority_vazhno() -> None:
    p = parse_quick_add("важно сделать отчёт", now=_NOW)
    assert p.priority == TaskPriority.P2


def test_word_priority_ne_srochno() -> None:
    p = parse_quick_add("разобрать ящик не срочно", now=_NOW)
    assert p.priority == TaskPriority.P3


def test_bang_beats_word_priority() -> None:
    """Bangs at end win over words inside text."""
    p = parse_quick_add("важно проверить бэкап !!!!", now=_NOW)
    assert p.priority == TaskPriority.P1


def test_through_hours_produces_datetime() -> None:
    p = parse_quick_add("позвонить через 2 часа", now=_NOW)
    assert p.due_at is not None
    assert p.date_only is False
    assert (p.due_at - _NOW) == timedelta(hours=2)


def test_through_minutes_produces_datetime() -> None:
    p = parse_quick_add("отправить через 30 минут", now=_NOW)
    assert p.due_at is not None
    assert p.date_only is False
    assert (p.due_at - _NOW) == timedelta(minutes=30)


def test_k_vyhodnym_picks_saturday() -> None:
    p = parse_quick_add("дочитать книгу к выходным", now=_NOW)
    assert p.due_at is not None
    # _NOW = Monday → next Saturday is +5 days
    assert p.due_at.weekday() == 5


def test_na_vyhodnyh_picks_saturday() -> None:
    p = parse_quick_add("гулять на выходных", now=_NOW)
    assert p.due_at is not None
    assert p.due_at.weekday() == 5


def test_evening_word_overlays_time() -> None:
    p = parse_quick_add("позвонить маме завтра вечером", now=_NOW)
    assert p.due_at is not None
    assert p.date_only is False
    assert p.due_at.hour == 20
    assert p.due_at.date() == (_NOW.date() + timedelta(days=1))


def test_morning_word_alone_uses_today() -> None:
    p = parse_quick_add("зарядка утром", now=_NOW)
    assert p.due_at is not None
    assert p.due_at.hour == 9
    assert p.due_at.date() == _NOW.date()


def test_after_lunch_overrides_lunch() -> None:
    """Multi-word phrase 'после обеда' must beat the single word 'обед'."""
    p = parse_quick_add("забрать посылку после обеда", now=_NOW)
    assert p.due_at is not None
    assert p.due_at.hour == 15


def test_recurrence_daily() -> None:
    p = parse_quick_add("медитация каждый день", now=_NOW)
    assert p.recurrence == "daily"
    assert "медитация" in p.title


def test_recurrence_weekly() -> None:
    p = parse_quick_add("отчёт каждую неделю", now=_NOW)
    assert p.recurrence == "weekly"


def test_recurrence_monthly() -> None:
    p = parse_quick_add("оплатить интернет каждый месяц", now=_NOW)
    assert p.recurrence == "monthly"


def test_recurrence_weekday_acc() -> None:
    p = parse_quick_add("спортзал каждый понедельник", now=_NOW)
    assert p.recurrence == "weekly"


def test_combo_word_priority_plus_through_hours() -> None:
    p = parse_quick_add("срочно перезвонить через 1 час", now=_NOW)
    assert p.priority == TaskPriority.P1
    assert p.due_at is not None
    assert p.date_only is False
    assert (p.due_at - _NOW) == timedelta(hours=1)


def test_combo_recurrence_plus_evening() -> None:
    p = parse_quick_add("прогулка каждый день вечером", now=_NOW)
    assert p.recurrence == "daily"
    assert p.due_at is not None
    assert p.due_at.hour == 20
    assert p.date_only is False


def test_existing_today_still_works() -> None:
    p = parse_quick_add("Купить хлеб сегодня", now=_NOW)
    assert p.due_at is not None
    assert p.due_at.date() == _NOW.date()
    assert p.title == "Купить хлеб"


def test_existing_bangs_still_work() -> None:
    p = parse_quick_add("Дочитать !!!", now=_NOW)
    assert p.priority == TaskPriority.P2
