"""Experimental-features opt-in: toggle endpoint + /app/graph gating."""

from httpx import AsyncClient


async def test_unknown_experiment_rejected(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.post(
        "/api/profile/experiments/bogus_feature", data={"enabled": "true"}
    )
    assert resp.status_code == 422


async def test_toggle_graph_experiment(logged_in_client: AsyncClient) -> None:
    # OFF by default → /app/graph redirects to settings.
    resp = await logged_in_client.get("/app/graph", follow_redirects=False)
    assert resp.status_code == 303
    assert "/app/settings" in resp.headers["location"]

    # Turn it ON.
    on = await logged_in_client.post("/api/profile/experiments/graph", data={"enabled": "true"})
    assert on.status_code == 200
    assert on.json() == {"enabled": True}

    # Now the page renders.
    resp2 = await logged_in_client.get("/app/graph")
    assert resp2.status_code == 200
    assert "Граф" in resp2.text or "graph" in resp2.text.lower()

    # And toggling OFF restores the gate.
    off = await logged_in_client.post("/api/profile/experiments/graph", data={"enabled": "false"})
    assert off.json() == {"enabled": False}
    resp3 = await logged_in_client.get("/app/graph", follow_redirects=False)
    assert resp3.status_code == 303


async def test_settings_page_lists_experiments(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/settings")).text
    assert "Экспериментальные функции" in body
    assert "Граф связей задач" in body


async def test_links_graph_api_returns_shape(logged_in_client: AsyncClient) -> None:
    """Even with zero tasks, /api/links/graph must return the {nodes, edges} shape."""
    resp = await logged_in_client.get("/api/links/graph")
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body and "edges" in body
    assert isinstance(body["nodes"], list) and isinstance(body["edges"], list)


async def test_create_link_between_two_tasks(logged_in_client: AsyncClient) -> None:
    """End-to-end: create two tasks, connect them, see the edge in the graph."""
    a = (await logged_in_client.post("/api/tasks", json={"title": "Source"})).json()
    b = (await logged_in_client.post("/api/tasks", json={"title": "Target"})).json()

    link = await logged_in_client.post(
        f"/api/tasks/{a['id']}/links",
        json={"target_task_id": b["id"], "note": "блокирует"},
    )
    assert link.status_code == 201
    assert link.json()["status"] == "ok"

    graph = (await logged_in_client.get("/api/links/graph")).json()
    # Both task nodes appear AND there's an edge from a→b.
    node_ids = {n["id"] for n in graph["nodes"]}
    assert a["id"] in node_ids and b["id"] in node_ids
    assert any(e.get("source") == a["id"] and e.get("target") == b["id"] for e in graph["edges"])


async def test_cant_link_task_to_itself(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "self"})).json()
    resp = await logged_in_client.post(
        f"/api/tasks/{t['id']}/links", json={"target_task_id": t["id"]}
    )
    assert resp.status_code == 422
