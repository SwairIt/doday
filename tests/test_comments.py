"""Tests for task comments — JSON CRUD + HTMX block."""

from httpx import AsyncClient


async def _make_task(client: AsyncClient) -> str:
    return (await client.post("/api/tasks", json={"title": "T"})).json()["id"]


async def test_create_and_list_comment(logged_in_client: AsyncClient) -> None:
    tid = await _make_task(logged_in_client)
    created = await logged_in_client.post(f"/api/tasks/{tid}/comments", json={"body": "первый"})
    assert created.status_code == 201
    listing = (await logged_in_client.get(f"/api/tasks/{tid}/comments")).json()
    assert len(listing) == 1
    assert listing[0]["body"] == "первый"


async def test_update_comment(logged_in_client: AsyncClient) -> None:
    tid = await _make_task(logged_in_client)
    c = (await logged_in_client.post(f"/api/tasks/{tid}/comments", json={"body": "v1"})).json()
    updated = (await logged_in_client.patch(f"/api/comments/{c['id']}", json={"body": "v2"})).json()
    assert updated["body"] == "v2"


async def test_delete_comment(logged_in_client: AsyncClient) -> None:
    tid = await _make_task(logged_in_client)
    c = (await logged_in_client.post(f"/api/tasks/{tid}/comments", json={"body": "x"})).json()
    response = await logged_in_client.delete(f"/api/comments/{c['id']}")
    assert response.status_code == 204
    assert (await logged_in_client.get(f"/api/tasks/{tid}/comments")).json() == []


async def test_htmx_comments_block_renders(logged_in_client: AsyncClient) -> None:
    tid = await _make_task(logged_in_client)
    await logged_in_client.post(f"/api/tasks/{tid}/comments", json={"body": "ping"})
    html = (await logged_in_client.get(f"/htmx/tasks/{tid}/comments")).text
    assert "ping" in html
    assert "Добавить комментарий" in html


async def test_htmx_comment_create_form(logged_in_client: AsyncClient) -> None:
    tid = await _make_task(logged_in_client)
    response = await logged_in_client.post(f"/htmx/tasks/{tid}/comments", data={"body": "via form"})
    assert response.status_code == 200
    assert "via form" in response.text


async def test_comment_on_unknown_task_404(logged_in_client: AsyncClient) -> None:
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await logged_in_client.post(f"/api/tasks/{fake_uuid}/comments", json={"body": "no"})
    assert response.status_code == 404
