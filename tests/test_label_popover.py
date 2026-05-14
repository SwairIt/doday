"""Tests for inline label popover on task_row."""

from httpx import AsyncClient


async def test_labels_popover_renders(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "urgent"})).json()
    html = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/labels-popover")).text
    assert "@urgent" in html
    assert "Новый лейбл" in html
    assert label["id"] in html or label["name"] in html


async def test_toggle_attach_then_detach(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "x"})).json()

    response = await logged_in_client.post(f"/htmx/tasks/{task['id']}/labels/{label['id']}/toggle")
    assert response.status_code == 200
    attached = (await logged_in_client.get(f"/api/tasks/{task['id']}/labels")).json()
    assert any(lab["id"] == label["id"] for lab in attached)

    await logged_in_client.post(f"/htmx/tasks/{task['id']}/labels/{label['id']}/toggle")
    attached2 = (await logged_in_client.get(f"/api/tasks/{task['id']}/labels")).json()
    assert all(lab["id"] != label["id"] for lab in attached2)


async def test_create_and_attach_new_label(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "T"})).json()
    response = await logged_in_client.post(
        f"/htmx/tasks/{task['id']}/labels/new", data={"name": "fresh"}
    )
    assert response.status_code == 200
    attached = (await logged_in_client.get(f"/api/tasks/{task['id']}/labels")).json()
    assert any(lab["name"] == "fresh" for lab in attached)


async def test_label_chips_render_in_task_row(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "WL"})).json()
    task = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "WithLab", "project_id": proj["id"]}
        )
    ).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "shown"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/labels/{label['id']}/toggle")

    page = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    # β redesign: task row shows first label inline as "— labelname" (no @ prefix).
    # Multi-label chips (with @) moved to detail panel; context-menu handles label edit.
    assert "shown" in page.text
