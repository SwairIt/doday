"""Tests for extended bulk actions: set_priority and move_project."""

from urllib.parse import urlencode

from httpx import AsyncClient


def _form(pairs: list[tuple[str, str]]) -> tuple[bytes, dict[str, str]]:
    body = urlencode(pairs).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    return body, headers


async def test_bulk_set_priority(logged_in_client: AsyncClient) -> None:
    t1 = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    t2 = (await logged_in_client.post("/api/tasks", json={"title": "B"})).json()

    body, headers = _form(
        [
            ("action", "set_priority"),
            ("priority", "p1"),
            ("ids", t1["id"]),
            ("ids", t2["id"]),
        ]
    )
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    by_id = {t["id"]: t for t in fetched}
    assert by_id[t1["id"]]["priority"] == "p1"
    assert by_id[t2["id"]]["priority"] == "p1"


async def test_bulk_move_project(logged_in_client: AsyncClient) -> None:
    src = (await logged_in_client.post("/api/projects", json={"name": "Src"})).json()
    dst = (await logged_in_client.post("/api/projects", json={"name": "Dst"})).json()
    t1 = (
        await logged_in_client.post("/api/tasks", json={"title": "X", "project_id": src["id"]})
    ).json()
    t2 = (
        await logged_in_client.post("/api/tasks", json={"title": "Y", "project_id": src["id"]})
    ).json()

    body, headers = _form(
        [
            ("action", "move_project"),
            ("project_id", dst["id"]),
            ("ids", t1["id"]),
            ("ids", t2["id"]),
        ]
    )
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    in_dst = (await logged_in_client.get(f"/api/tasks?project_id={dst['id']}")).json()
    titles = {t["title"] for t in in_dst}
    assert {"X", "Y"} <= titles
    in_src = (await logged_in_client.get(f"/api/tasks?project_id={src['id']}")).json()
    assert all(t["title"] not in {"X", "Y"} for t in in_src)


async def test_bulk_set_priority_invalid(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "Z"})).json()
    body, headers = _form([("action", "set_priority"), ("priority", "p9"), ("ids", t["id"])])
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 400


async def test_bulk_move_project_unknown(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "Z"})).json()
    body, headers = _form(
        [
            ("action", "move_project"),
            ("project_id", "00000000-0000-0000-0000-000000000000"),
            ("ids", t["id"]),
        ]
    )
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 404


async def test_bulk_set_due(logged_in_client: AsyncClient) -> None:
    t1 = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    t2 = (await logged_in_client.post("/api/tasks", json={"title": "B"})).json()
    body, headers = _form(
        [
            ("action", "set_due"),
            ("due", "2026-12-31"),
            ("ids", t1["id"]),
            ("ids", t2["id"]),
        ]
    )
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    by_id = {t["id"]: t for t in fetched}
    assert by_id[t1["id"]]["due_at"].startswith("2026-12-31")
    assert by_id[t2["id"]]["due_at"].startswith("2026-12-31")


async def test_bulk_clear_due(logged_in_client: AsyncClient) -> None:
    t = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "X", "due_at": "2026-06-15T00:00:00Z"}
        )
    ).json()
    body, headers = _form([("action", "set_due"), ("due", ""), ("ids", t["id"])])
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    fetched = (await logged_in_client.get("/api/tasks")).json()
    assert next(x for x in fetched if x["id"] == t["id"])["due_at"] is None


async def test_bulk_set_due_invalid(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "Z"})).json()
    body, headers = _form([("action", "set_due"), ("due", "not-a-date"), ("ids", t["id"])])
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 400


async def test_bulk_attach_label(logged_in_client: AsyncClient) -> None:
    t1 = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    t2 = (await logged_in_client.post("/api/tasks", json={"title": "B"})).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "bulk"})).json()
    body, headers = _form(
        [
            ("action", "attach_label"),
            ("label_id", label["id"]),
            ("ids", t1["id"]),
            ("ids", t2["id"]),
        ]
    )
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    for tid in (t1["id"], t2["id"]):
        attached = (await logged_in_client.get(f"/api/tasks/{tid}/labels")).json()
        assert any(lab["id"] == label["id"] for lab in attached)


async def test_bulk_detach_label(logged_in_client: AsyncClient) -> None:
    t = (await logged_in_client.post("/api/tasks", json={"title": "A"})).json()
    label = (await logged_in_client.post("/api/labels", json={"name": "tmp"})).json()
    await logged_in_client.post(f"/doday/htmx/tasks/{t['id']}/labels/{label['id']}/toggle")
    body, headers = _form([("action", "detach_label"), ("label_id", label["id"]), ("ids", t["id"])])
    response = await logged_in_client.post("/doday/htmx/bulk", content=body, headers=headers)
    assert response.status_code == 200
    attached = (await logged_in_client.get(f"/api/tasks/{t['id']}/labels")).json()
    assert all(lab["id"] != label["id"] for lab in attached)
