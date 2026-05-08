"""Tests for the cosmic graph view: API + page render."""

from httpx import AsyncClient


async def test_graph_api_empty(logged_in_client: AsyncClient) -> None:
    """Fresh user with no tasks — empty graph payload."""
    r = await logged_in_client.get("/api/links/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body
    # Welcome flow seeds a few sample tasks; just sanity-check the shape.
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)


async def test_graph_includes_links_and_parents(logged_in_client: AsyncClient) -> None:
    """Tasks with explicit links and parent-child relationships show up as edges."""
    a = (await logged_in_client.post("/api/tasks", json={"title": "alpha"})).json()
    b = (await logged_in_client.post("/api/tasks", json={"title": "beta"})).json()
    c = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "gamma child", "parent_task_id": a["id"]}
        )
    ).json()
    await logged_in_client.post(f"/api/tasks/{a['id']}/links", json={"target_task_id": b["id"]})

    body = (await logged_in_client.get("/api/links/graph")).json()
    ids = {n["id"] for n in body["nodes"]}
    assert a["id"] in ids
    assert b["id"] in ids
    assert c["id"] in ids

    kinds_for_a = [e for e in body["edges"] if a["id"] in (e["source"], e["target"])]
    assert any(e["kind"] == "link" for e in kinds_for_a)
    assert any(e["kind"] == "parent" for e in kinds_for_a)


async def test_graph_view_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/graph")).text
    assert "Граф задач" in body
    assert "graph-canvas" in body
    assert "/api/links/graph" in body


async def test_graph_view_anon_blocked(client: AsyncClient) -> None:
    assert (await client.get("/app/graph")).status_code == 401


async def test_graph_api_anon_blocked(client: AsyncClient) -> None:
    assert (await client.get("/api/links/graph")).status_code == 401


async def test_sidebar_links_graph(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "/app/graph" in body
