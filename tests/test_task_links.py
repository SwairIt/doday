"""Tests for the task-link API — create, list (in/out direction), delete, cross-project."""

from httpx import AsyncClient


async def _new_task(
    client: AsyncClient, title: str, project_id: str | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"title": title}
    if project_id:
        body["project_id"] = project_id
    result: dict[str, object] = (await client.post("/api/tasks", json=body)).json()
    return result


async def test_link_create_and_list(logged_in_client: AsyncClient) -> None:
    a = await _new_task(logged_in_client, "Task A")
    b = await _new_task(logged_in_client, "Task B")

    r = await logged_in_client.post(
        f"/api/tasks/{a['id']}/links",
        json={"target_task_id": b["id"], "note": "depends on"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "ok"

    # outgoing link visible from A
    out_a = (await logged_in_client.get(f"/api/tasks/{a['id']}/links")).json()
    assert len(out_a) == 1
    assert out_a[0]["task_id"] == b["id"]
    assert out_a[0]["direction"] == "outgoing"
    assert out_a[0]["note"] == "depends on"

    # backlink visible from B
    out_b = (await logged_in_client.get(f"/api/tasks/{b['id']}/links")).json()
    assert len(out_b) == 1
    assert out_b[0]["task_id"] == a["id"]
    assert out_b[0]["direction"] == "incoming"


async def test_link_self_rejected(logged_in_client: AsyncClient) -> None:
    a = await _new_task(logged_in_client, "Loop")
    r = await logged_in_client.post(
        f"/api/tasks/{a['id']}/links",
        json={"target_task_id": a["id"]},
    )
    assert r.status_code == 422


async def test_link_idempotent(logged_in_client: AsyncClient) -> None:
    """Posting the same link twice doesn't duplicate it."""
    a = await _new_task(logged_in_client, "A")
    b = await _new_task(logged_in_client, "B")
    await logged_in_client.post(f"/api/tasks/{a['id']}/links", json={"target_task_id": b["id"]})
    r = await logged_in_client.post(f"/api/tasks/{a['id']}/links", json={"target_task_id": b["id"]})
    assert r.status_code == 201  # second call returns 201 too, but no duplicate
    out = (await logged_in_client.get(f"/api/tasks/{a['id']}/links")).json()
    assert len(out) == 1


async def test_link_cross_project(logged_in_client: AsyncClient) -> None:
    """Links between tasks in different projects are allowed."""
    p1 = (await logged_in_client.post("/api/projects", json={"name": "P1"})).json()
    p2 = (await logged_in_client.post("/api/projects", json={"name": "P2"})).json()
    a = await _new_task(logged_in_client, "in P1", project_id=p1["id"])
    b = await _new_task(logged_in_client, "in P2", project_id=p2["id"])

    r = await logged_in_client.post(f"/api/tasks/{a['id']}/links", json={"target_task_id": b["id"]})
    assert r.status_code == 201

    out = (await logged_in_client.get(f"/api/tasks/{a['id']}/links")).json()
    assert out[0]["project_name"] == "P2"
    assert out[0]["project_id"] == p2["id"]


async def test_link_delete(logged_in_client: AsyncClient) -> None:
    a = await _new_task(logged_in_client, "A")
    b = await _new_task(logged_in_client, "B")
    create = await logged_in_client.post(
        f"/api/tasks/{a['id']}/links", json={"target_task_id": b["id"]}
    )
    link_id = create.json()["id"]

    r = await logged_in_client.delete(f"/api/tasks/{a['id']}/links/{link_id}")
    assert r.status_code == 204

    out = (await logged_in_client.get(f"/api/tasks/{a['id']}/links")).json()
    assert out == []


async def test_link_delete_idempotent_missing(logged_in_client: AsyncClient) -> None:
    a = await _new_task(logged_in_client, "A")
    # bogus link_id → 404
    r = await logged_in_client.delete(
        f"/api/tasks/{a['id']}/links/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404


async def test_link_anon_blocked(client: AsyncClient) -> None:
    r = await client.get("/api/tasks/00000000-0000-0000-0000-000000000000/links")
    assert r.status_code == 401
