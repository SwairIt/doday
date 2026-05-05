"""Smoke tests for the task-keyboard navigation partial wired into app_base."""

from httpx import AsyncClient


async def test_keyboard_partial_loaded(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # Markers unique to the task_keyboard partial.
    assert "data-kb-selected" in body
    assert "task-wrap-" in body or "/htmx/tasks/" in body  # hooks the partial uses


async def test_shortcuts_overlay_lists_new_hotkeys(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # New section in the ? overlay listing per-task hotkeys.
    assert "На выделенной задаче" in body
    assert "Поставить приоритет" in body
    assert "Сегодня / завтра / к концу недели" in body
