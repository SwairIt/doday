"""Tests for project templates: list + instantiate."""

from httpx import AsyncClient


async def test_list_templates(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/projects/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    keys = {t["key"] for t in data}
    assert "weekly-planning" in keys
    assert "school" in keys


async def test_template_response_shape(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/projects/templates")
    first = response.json()[0]
    assert {"key", "name", "icon", "color", "description", "sections_count", "tasks_count"} <= set(
        first.keys()
    )


async def test_create_project_from_template(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects/from-template", json={"template_key": "school"}
    )
    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "Учёба"
    assert project["color"] == "amber"

    sections = (await logged_in_client.get(f"/api/sections?project_id={project['id']}")).json()
    assert len(sections) == 3
    section_names = {s["name"] for s in sections}
    assert {"Домашка", "Проекты", "Экзамены"} == section_names

    tasks = (await logged_in_client.get(f"/api/tasks?project_id={project['id']}")).json()
    assert len(tasks) >= 3
    titles = {t["title"] for t in tasks}
    assert "Сделать уроки на завтра" in titles


async def test_create_from_template_with_custom_name(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects/from-template",
        json={"template_key": "trip", "name": "Поездка в Питер"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Поездка в Питер"


async def test_create_from_unknown_template(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects/from-template", json={"template_key": "no-such-template"}
    )
    assert response.status_code == 404
