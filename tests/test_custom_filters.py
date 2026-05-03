"""Tests for user-defined custom filters: CRUD + execution semantics."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_create_and_list_custom_filter(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/custom-filters",
        json={
            "name": "Срочное",
            "color": "rose",
            "query": {"priorities": ["p1"]},
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Срочное"
    assert response.json()["query"]["priorities"] == ["p1"]

    listing = (await logged_in_client.get("/api/custom-filters")).json()
    assert any(f["name"] == "Срочное" for f in listing)


async def test_update_custom_filter(logged_in_client: AsyncClient) -> None:
    cf = (
        await logged_in_client.post(
            "/api/custom-filters",
            json={"name": "F1", "query": {"priorities": ["p3"]}},
        )
    ).json()
    updated = (
        await logged_in_client.patch(
            f"/api/custom-filters/{cf['id']}",
            json={"name": "F1+", "query": {"priorities": ["p1", "p2"]}},
        )
    ).json()
    assert updated["name"] == "F1+"
    assert set(updated["query"]["priorities"]) == {"p1", "p2"}


async def test_delete_custom_filter(logged_in_client: AsyncClient) -> None:
    cf = (await logged_in_client.post("/api/custom-filters", json={"name": "Tmp"})).json()
    response = await logged_in_client.delete(f"/api/custom-filters/{cf['id']}")
    assert response.status_code == 204
    assert all(
        f["id"] != cf["id"] for f in (await logged_in_client.get("/api/custom-filters")).json()
    )


async def test_filter_view_renders_only_matching_tasks(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "FProj"})).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "Hot", "project_id": proj["id"], "priority": "p1"}
    )
    await logged_in_client.post(
        "/api/tasks", json={"title": "Cold", "project_id": proj["id"], "priority": "p4"}
    )

    cf = (
        await logged_in_client.post(
            "/api/custom-filters",
            json={"name": "Только P1", "query": {"priorities": ["p1"]}},
        )
    ).json()

    page = await logged_in_client.get(f"/app/filters/custom/{cf['id']}")
    assert page.status_code == 200
    assert "Hot" in page.text
    assert "Cold" not in page.text


async def test_filter_due_today(logged_in_client: AsyncClient) -> None:
    today_iso = datetime.now(UTC).date().isoformat() + "T12:00:00Z"
    tomorrow_iso = (datetime.now(UTC) + timedelta(days=2)).date().isoformat() + "T12:00:00Z"
    await logged_in_client.post("/api/tasks", json={"title": "DueNow", "due_at": today_iso})
    await logged_in_client.post("/api/tasks", json={"title": "DueLater", "due_at": tomorrow_iso})
    cf = (
        await logged_in_client.post(
            "/api/custom-filters",
            json={"name": "Today", "query": {"due_window": "today"}},
        )
    ).json()
    page = await logged_in_client.get(f"/app/filters/custom/{cf['id']}")
    assert "DueNow" in page.text
    assert "DueLater" not in page.text


async def test_filter_text_search(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/tasks", json={"title": "купить молоко"})
    await logged_in_client.post("/api/tasks", json={"title": "позвонить маме"})
    cf = (
        await logged_in_client.post(
            "/api/custom-filters",
            json={"name": "Магазин", "query": {"has_text": "молок"}},
        )
    ).json()
    page = await logged_in_client.get(f"/app/filters/custom/{cf['id']}")
    assert "купить молоко" in page.text
    assert "позвонить маме" not in page.text


async def test_manage_page_renders(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/custom-filters", json={"name": "Listed"})
    page = await logged_in_client.get("/app/filters")
    assert page.status_code == 200
    assert "Listed" in page.text
    assert "Новый фильтр" in page.text


async def test_unknown_filter_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get(
        "/app/filters/custom/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
