"""Tests for POST /api/tasks/bulk — multi-line paste import."""

from datetime import UTC, datetime

from httpx import AsyncClient


async def test_bulk_create_three_titles(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/tasks/bulk",
        json={"titles": ["First task", "Second task", "Third task"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 3
    titles = [t["title"] for t in body]
    assert titles == ["First task", "Second task", "Third task"]


async def test_bulk_create_drops_empty_lines(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/tasks/bulk",
        json={"titles": ["A", "  ", "", "B"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 2
    assert [t["title"] for t in body] == ["A", "B"]


async def test_bulk_create_all_empty_400(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/tasks/bulk", json={"titles": ["", "  ", "\t"]})
    assert response.status_code == 400


async def test_bulk_create_with_common_due(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T18:00:00Z"
    response = await logged_in_client.post(
        "/api/tasks/bulk",
        json={"titles": ["X", "Y"], "common_due_at": today_iso},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 2
    for t in body:
        assert t["due_at"] is not None


async def test_bulk_create_into_specific_project(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Bulk target"})).json()
    response = await logged_in_client.post(
        "/api/tasks/bulk",
        json={"project_id": proj["id"], "titles": ["A", "B"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert all(t["project_id"] == proj["id"] for t in body)


async def test_bulk_create_unknown_project_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/tasks/bulk",
        json={"project_id": "00000000-0000-0000-0000-000000000000", "titles": ["X"]},
    )
    assert response.status_code == 404


async def test_bulk_truncates_long_title(logged_in_client: AsyncClient) -> None:
    long = "A" * 1000
    response = await logged_in_client.post("/api/tasks/bulk", json={"titles": [long]})
    assert response.status_code == 201
    assert len(response.json()[0]["title"]) == 500
