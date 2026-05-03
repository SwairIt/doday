"""Tests for project Markdown export and mobile bottom-nav inclusion."""

from httpx import AsyncClient


async def test_export_md_renders_title_and_tasks(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "MdProj"})).json()
    await logged_in_client.patch(f"/api/projects/{proj['id']}", json={"description": "Описание"})
    await logged_in_client.post(
        "/api/tasks", json={"title": "First task", "project_id": proj["id"], "priority": "p1"}
    )

    response = await logged_in_client.get(f"/api/projects/{proj['id']}/export.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "# MdProj" in body
    assert "Описание" in body
    assert "- [ ] First task" in body
    assert "!1" in body  # priority annotation


async def test_export_md_groups_by_section(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Grouped"})).json()
    sec = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj["id"], "name": "Doing"}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "InSection", "project_id": proj["id"], "section_id": sec["id"]},
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.md")).text
    assert "## Doing" in body
    assert "InSection" in body


async def test_export_md_indents_subtasks(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Sub"})).json()
    parent = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Parent", "project_id": proj["id"]}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Child", "project_id": proj["id"], "parent_task_id": parent["id"]},
    )
    body = (await logged_in_client.get(f"/api/projects/{proj['id']}/export.md")).text
    assert "- [ ] Parent" in body
    assert "  - [ ] Child" in body  # two-space indent


async def test_export_md_unknown_project_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get(
        "/api/projects/00000000-0000-0000-0000-000000000000/export.md"
    )
    assert response.status_code == 404


async def test_mobile_nav_present(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/app/today")
    assert page.status_code == 200
    # Bottom-nav has md:hidden + Inbox/Сегодня/Календарь labels visible to phones.
    assert "md:hidden" in page.text
    # All five nav labels appear.
    for label in ["Inbox", "Сегодня", "Дальше", "Календарь", "Профиль"]:
        assert label in page.text
