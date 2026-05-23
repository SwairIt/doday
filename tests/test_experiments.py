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


# --- calendar_feed experiment ----------------------------------------------


async def test_ical_token_gated_by_calendar_feed_experiment(
    logged_in_client: AsyncClient,
) -> None:
    """Without the calendar_feed experiment, issuing an ical token is 403."""
    resp = await logged_in_client.get("/api/profile/ical-token")
    assert resp.status_code == 403


async def test_ical_token_issued_after_enabling_experiment(
    logged_in_client: AsyncClient,
) -> None:
    on = await logged_in_client.post(
        "/api/profile/experiments/calendar_feed", data={"enabled": "true"}
    )
    assert on.json()["enabled"] is True

    resp = await logged_in_client.get("/api/profile/ical-token")
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body and len(body["token"]) >= 24
    assert body["url"].endswith(".ics")


async def test_habits_view_gated(logged_in_client: AsyncClient) -> None:
    """Without the habits experiment, /app/habits redirects to settings."""
    resp = await logged_in_client.get("/app/habits", follow_redirects=False)
    assert resp.status_code == 303
    assert "/app/settings" in resp.headers["location"]

    on = await logged_in_client.post("/api/profile/experiments/habits", data={"enabled": "true"})
    assert on.json()["enabled"] is True

    resp2 = await logged_in_client.get("/app/habits")
    assert resp2.status_code == 200


async def test_ics_feed_serves_when_token_known(logged_in_client: AsyncClient) -> None:
    """The public-by-token .ics endpoint works regardless of the experiment flag —
    so a calendar subscription that was set up earlier doesn't break if the user
    toggles the experiment off."""
    await logged_in_client.post("/api/profile/experiments/calendar_feed", data={"enabled": "true"})
    token = (await logged_in_client.get("/api/profile/ical-token")).json()["token"]
    # Use the unauthenticated client (no cookies) to confirm public-by-token.
    from httpx import ASGITransport
    from httpx import AsyncClient as PlainClient

    from app.main import app

    async with PlainClient(transport=ASGITransport(app=app), base_url="http://test") as plain:
        resp = await plain.get(f"/api/calendar/feed/{token}.ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in resp.text
