"""Tests for the task detail slideover panel."""

from httpx import AsyncClient


async def test_detail_renders_title_and_description(logged_in_client: AsyncClient) -> None:
    task = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Detail title", "description": "Body text"}
        )
    ).json()
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{task['id']}/detail")).text
    assert "Detail title" in html
    assert "Body text" in html
    assert "Приоритет" in html
    assert "Срок" in html
    assert "Лейблы" in html
    assert "Комментарии" in html


async def test_detail_save_updates_title_and_description(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Old"})).json()
    response = await logged_in_client.patch(
        f"/doday/htmx/tasks/{task['id']}/detail",
        data={"title": "New", "description": "Now described"},
    )
    assert response.status_code == 200
    assert "New" in response.text
    fetched = (await logged_in_client.get("/api/tasks?include_completed=true")).json()
    saved = next(t for t in fetched if t["id"] == task["id"])
    assert saved["title"] == "New"
    assert saved["description"] == "Now described"


async def test_detail_lists_subtasks(logged_in_client: AsyncClient) -> None:
    parent = (await logged_in_client.post("/api/tasks", json={"title": "Parent"})).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "Sub one", "parent_task_id": parent["id"]}
    )
    await logged_in_client.post(
        "/api/tasks", json={"title": "Sub two", "parent_task_id": parent["id"]}
    )
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{parent['id']}/detail")).text
    assert "Sub one" in html
    assert "Sub two" in html


async def test_detail_lists_attached_labels(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "lab"})).json()
    await logged_in_client.post(f"/doday/htmx/tasks/{task['id']}/labels/{label['id']}/toggle")
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{task['id']}/detail")).text
    assert "@lab" in html


async def test_detail_lists_comments(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    await logged_in_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "first comment"})
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{task['id']}/detail")).text
    assert "first comment" in html


async def test_detail_open_trigger_in_task_row(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Trig"})).json()
    await logged_in_client.post("/api/tasks", json={"title": "ClickMe", "project_id": proj["id"]})
    page = await logged_in_client.get(f"/doday/app/projects/{proj['slug']}")
    assert 'hx-get="/doday/htmx/tasks/' in page.text
    assert "/detail" in page.text
    assert 'id="task-detail-slot"' in page.text


async def test_detail_unknown_task_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get(
        "/doday/htmx/tasks/00000000-0000-0000-0000-000000000000/detail"
    )
    assert response.status_code == 404


async def test_detail_includes_pomodoro_widget(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Focus"})).json()
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{task['id']}/detail")).text
    assert "Помидор" in html
    assert "Работа 25" in html
    assert "Перерыв 5" in html
