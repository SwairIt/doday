"""Tests for inline edit (C15-extended) and search palette (C16)."""

from httpx import AsyncClient


async def test_edit_form_returned(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "Original"})
    task_id = create.json()["id"]

    form = await logged_in_client.get(f"/doday/htmx/tasks/{task_id}/edit")
    assert form.status_code == 200
    assert "Сохранить" in form.text
    assert "Отмена" in form.text
    assert 'value="Original"' in form.text


async def test_edit_save_updates_title(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "Old"})
    task_id = create.json()["id"]

    save = await logged_in_client.patch(f"/doday/htmx/tasks/{task_id}", data={"title": "New title"})
    assert save.status_code == 200
    assert "New title" in save.text
    assert "task-row" in save.text  # rendered as row partial again

    # Verify in DB via API
    after = await logged_in_client.get("/api/tasks")
    assert any(t["title"] == "New title" for t in after.json())


async def test_get_row_returns_readonly_row(logged_in_client: AsyncClient) -> None:
    create = await logged_in_client.post("/api/tasks", json={"title": "Some task"})
    task_id = create.json()["id"]

    row = await logged_in_client.get(f"/doday/htmx/tasks/{task_id}/row")
    assert row.status_code == 200
    assert "Some task" in row.text
    assert "task-row" in row.text


async def test_search_short_query_returns_hint(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/htmx/search?q=a")
    assert response.status_code == 200
    assert "минимум" in response.text.lower()


async def test_search_finds_task_by_title(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "Купить картошку"})
    await logged_in_client.post("/api/tasks", json={"title": "Сделать домашку"})

    response = await logged_in_client.get("/doday/htmx/search?q=карто")
    assert response.status_code == 200
    assert "Купить картошку" in response.text
    assert "Сделать домашку" not in response.text


async def test_search_finds_project_by_name(logged_in_client: AsyncClient) -> None:
    """ASCII case-insensitive search — Cyrillic ICU collation is a separate task."""
    await logged_in_client.post("/api/projects", json={"name": "Work", "color": "violet"})
    response = await logged_in_client.get("/doday/htmx/search?q=wor")
    assert response.status_code == 200
    assert "Work" in response.text
    assert "проект" in response.text


async def test_search_empty_results(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/htmx/search?q=абракадабра12345")
    assert response.status_code == 200
    assert "не нашёл" in response.text.lower()
