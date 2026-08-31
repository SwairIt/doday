"""Tests for the quick-add NL parser + endpoint."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.quickadd.parser import parse_quick_add
from app.tasks.models import TaskPriority

_FIXED_NOW = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)  # Sunday


def test_parser_extracts_priority_high() -> None:
    p = parse_quick_add("Срочный отчёт !!!!", now=_FIXED_NOW)
    assert p.title == "Срочный отчёт"
    assert p.priority is TaskPriority.P1


def test_parser_single_bang_is_p3_not_default() -> None:
    # Одна «!» должна давать видимый приоритет (P3), а не дефолтный P4.
    p = parse_quick_add("Полить цветы !", now=_FIXED_NOW)
    assert p.title == "Полить цветы"
    assert p.priority is TaskPriority.P3


def test_parser_bangs_in_the_middle() -> None:
    # «!» отдельным токеном в середине строки — тоже приоритет, а не часть
    # названия (регрессия: раньше ловилось только в самом конце).
    p = parse_quick_add("Сделать !! завтра", now=_FIXED_NOW)
    assert p.title == "Сделать"
    assert p.priority is TaskPriority.P2
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(days=1)).date()


def test_parser_user_scenario_label_date_bangs() -> None:
    # Точный кейс из поддержки: метка + срок + «!!!» в середине + ведущий «:».
    p = parse_quick_add("@Швейцар сегодня !!! : Исправить 2 бага", now=_FIXED_NOW)
    assert p.priority is TaskPriority.P1  # 3 bangs → максимум
    assert p.label_names == ["Швейцар"]
    assert p.due_at is not None and p.due_at.date() == _FIXED_NOW.date()
    assert p.title == "Исправить 2 бага"  # без «!!!», без ведущего «:»


def test_parser_no_priority_default_p4() -> None:
    p = parse_quick_add("Just a thing", now=_FIXED_NOW)
    assert p.priority is TaskPriority.P4


def test_parser_today_keyword() -> None:
    p = parse_quick_add("Сходить в магазин сегодня", now=_FIXED_NOW)
    assert p.title == "Сходить в магазин"
    assert p.due_at is not None
    assert p.due_at.date() == _FIXED_NOW.date()
    assert p.due_at.hour == 23 and p.due_at.minute == 59


def test_parser_tomorrow_keyword() -> None:
    p = parse_quick_add("Зайти в банк завтра", now=_FIXED_NOW)
    assert p.title == "Зайти в банк"
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(days=1)).date()


def test_parser_weekday_short() -> None:
    # Sunday _FIXED_NOW; "пт" → next Friday (5 days ahead)
    p = parse_quick_add("Контрольная пт", now=_FIXED_NOW)
    assert p.title == "Контрольная"
    assert p.due_at is not None
    assert p.due_at.weekday() == 4


def test_parser_dd_mm() -> None:
    p = parse_quick_add("Билеты 15.06", now=_FIXED_NOW)
    assert p.title == "Билеты"
    assert p.due_at is not None
    assert p.due_at.month == 6 and p.due_at.day == 15


def test_parser_project_hint() -> None:
    p = parse_quick_add("Сделать дизайн #работа", now=_FIXED_NOW)
    assert p.title == "Сделать дизайн"
    assert p.project_name == "работа"


def test_parser_labels() -> None:
    p = parse_quick_add("Сходить @спорт @вечер", now=_FIXED_NOW)
    assert p.title == "Сходить"
    assert p.label_names == ["спорт", "вечер"]


def test_parser_combined() -> None:
    p = parse_quick_add(
        "Записаться на массаж завтра @здоровье !!!",
        now=_FIXED_NOW,
    )
    assert p.title == "Записаться на массаж"
    assert p.priority is TaskPriority.P1  # 3 bangs → максимум
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(days=1)).date()
    assert p.label_names == ["здоровье"]


def test_parser_email_address_not_label() -> None:
    """An @ inside a word shouldn't be treated as a label."""
    p = parse_quick_add("Написать письмо foo@bar.com", now=_FIXED_NOW)
    # `@bar.com` is preceded by a letter, so the (?<!\w)@ guard skips it.
    assert p.label_names == []
    assert "foo@bar.com" in p.title


def test_parser_empty_falls_back() -> None:
    p = parse_quick_add("   !!!", now=_FIXED_NOW)
    assert p.title == "(без названия)"
    assert p.priority is TaskPriority.P1


@pytest.mark.asyncio
async def test_quickadd_endpoint_creates_task(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/htmx/quickadd", data={"text": "Хлеб купить завтра !!"})
    assert response.status_code == 200
    assert "task-row" in response.text
    assert "Хлеб купить" in response.text


@pytest.mark.asyncio
async def test_quickadd_attaches_label(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/htmx/quickadd", data={"text": "Прибраться @дом"})
    assert response.status_code == 200

    # Verify the label was created
    labels = await logged_in_client.get("/api/labels")
    assert any(lab["name"] == "дом" for lab in labels.json())


def test_parser_through_n_days() -> None:
    p = parse_quick_add("Позвонить через 5 дней", now=_FIXED_NOW)
    assert p.title == "Позвонить"
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(days=5)).date()


def test_parser_through_one_day_implicit() -> None:
    p = parse_quick_add("Зайти через день", now=_FIXED_NOW)
    assert p.title == "Зайти"
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(days=1)).date()


def test_parser_through_week() -> None:
    p = parse_quick_add("Отчёт через неделю", now=_FIXED_NOW)
    assert p.title == "Отчёт"
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(weeks=1)).date()


def test_parser_through_two_weeks() -> None:
    p = parse_quick_add("Спринт через 2 недели", now=_FIXED_NOW)
    assert p.title == "Спринт"
    assert p.due_at is not None
    assert p.due_at.date() == (_FIXED_NOW + timedelta(weeks=2)).date()


def test_parser_through_month() -> None:
    p = parse_quick_add("Подвести итоги через месяц", now=_FIXED_NOW)
    assert p.title == "Подвести итоги"
    assert p.due_at is not None
    assert p.due_at.date() == datetime(2026, 6, 3, tzinfo=UTC).date()


def test_calendar_month_clamps_end_of_month() -> None:
    now = datetime(2026, 1, 31, 12, tzinfo=UTC)
    p = parse_quick_add("Оплатить через месяц", now=now)
    assert p.due_at is not None
    assert p.due_at.date() == datetime(2026, 2, 28, tzinfo=UTC).date()


def test_tomorrow_uses_users_timezone_and_parses_explicit_time() -> None:
    # 21:30 UTC is already 00:30 on 4 May in Moscow. "Tomorrow 18:00"
    # therefore means 5 May 18:00 MSK = 15:00 UTC.
    now = datetime(2026, 5, 3, 21, 30, tzinfo=UTC)
    p = parse_quick_add(
        "Сдать реферат завтра в 18:00 !!! @школа",
        now=now,
        timezone_name="Europe/Moscow",
    )
    assert p.title == "Сдать реферат"
    assert p.due_at == datetime(2026, 5, 5, 15, 0, tzinfo=UTC)
    assert p.date_only is False
    assert p.priority is TaskPriority.P1
    assert p.label_names == ["школа"]


def test_weekday_recurrence_gets_first_due_date() -> None:
    p = parse_quick_add("Тренировка каждый понедельник", now=_FIXED_NOW)
    assert p.recurrence == "weekly"
    assert p.due_at is not None
    assert p.due_at.date() == datetime(2026, 5, 4, tzinfo=UTC).date()


def test_label_does_not_swallow_punctuation() -> None:
    p = parse_quick_add("Купить молоко @магазин, завтра", now=_FIXED_NOW)
    assert p.label_names == ["магазин"]
    assert p.title == "Купить молоко"


def test_parser_day_month_words() -> None:
    p = parse_quick_add("Купить подарок 15 декабря", now=_FIXED_NOW)
    assert p.title == "Купить подарок"
    assert p.due_at is not None
    assert p.due_at.month == 12 and p.due_at.day == 15


def test_parser_day_month_past_rolls_to_next_year() -> None:
    # 1 января has already passed in 2026 (today is 3 May 2026) → roll to 2027
    p = parse_quick_add("Поздравить 1 января", now=_FIXED_NOW)
    assert p.due_at is not None
    assert p.due_at.year == 2027 and p.due_at.month == 1 and p.due_at.day == 1


def test_parser_next_weekday_prefix_skips_a_week() -> None:
    # _FIXED_NOW is Sunday 2026-05-03. Monday is +1 day; «след пн» should be +8 days.
    p = parse_quick_add("Встреча след пн", now=_FIXED_NOW)
    assert p.due_at is not None
    assert p.due_at.weekday() == 0
    assert (p.due_at.date() - _FIXED_NOW.date()).days == 8
