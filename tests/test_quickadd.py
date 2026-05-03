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


def test_parser_extracts_priority_low() -> None:
    p = parse_quick_add("Полить цветы !", now=_FIXED_NOW)
    assert p.title == "Полить цветы"
    assert p.priority is TaskPriority.P4


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
    assert p.priority is TaskPriority.P2  # 3 bangs
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
    assert p.priority is TaskPriority.P2


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
