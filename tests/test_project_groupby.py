"""Tests that the project view ships the group-by toggle (priority / date / none)."""

from httpx import AsyncClient


async def test_project_view_has_groupby_dropdown(logged_in_client: AsyncClient) -> None:
    """The project page exposes a group-by dropdown alongside sort."""
    proj = (await logged_in_client.post("/api/projects", json={"name": "Test"})).json()
    body = (await logged_in_client.get(f"/app/projects/{proj['slug']}")).text
    assert "Группа:" in body
    assert "Без группировки" in body
    assert "По приоритету" in body
    assert "По дате" in body
    assert "doday-group-" in body


async def test_project_view_marks_no_section_block(logged_in_client: AsyncClient) -> None:
    """The no-section task list is wrapped in #no-section-block so group-by can hide it."""
    proj = (await logged_in_client.post("/api/projects", json={"name": "G"})).json()
    await logged_in_client.post(
        "/api/tasks", json={"title": "loose task", "project_id": proj["id"]}
    )
    body = (await logged_in_client.get(f"/app/projects/{proj['slug']}")).text
    assert 'id="no-section-block"' in body
