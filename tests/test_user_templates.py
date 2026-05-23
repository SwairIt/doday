"""Tests for user-saved project templates: snapshot + instantiate."""

from httpx import AsyncClient


async def test_save_project_as_template(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "SrcProj"})).json()
    sec = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj["id"], "name": "TodoCol"}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={
            "title": "First",
            "project_id": proj["id"],
            "section_id": sec["id"],
            "priority": "p1",
        },
    )
    response = await logged_in_client.post(
        f"/api/projects/{proj['id']}/save-as-template",
        json={"name": "My SrcProj template"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My SrcProj template"
    assert len(body["payload"]["sections"]) == 1
    assert len(body["payload"]["tasks"]) == 1
    assert body["payload"]["tasks"][0]["title"] == "First"
    assert body["payload"]["tasks"][0]["priority"] == "p1"


async def test_list_user_templates(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "X"})).json()
    await logged_in_client.post(f"/api/projects/{proj['id']}/save-as-template", json={})
    listing = (await logged_in_client.get("/api/user-templates")).json()
    assert any(t["name"].startswith("Шаблон: X") or t["name"] == "X" for t in listing)


async def test_instantiate_user_template(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "ToClone"})).json()
    parent = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "Parent", "project_id": proj["id"]}
        )
    ).json()
    await logged_in_client.post(
        "/api/tasks",
        json={"title": "Child", "project_id": proj["id"], "parent_task_id": parent["id"]},
    )
    tpl = (
        await logged_in_client.post(
            f"/api/projects/{proj['id']}/save-as-template", json={"name": "MyTpl"}
        )
    ).json()
    new_proj = (
        await logged_in_client.post(
            f"/api/user-templates/{tpl['id']}/instantiate",
            json={"name": "FromTpl"},
        )
    ).json()
    assert new_proj["name"] == "FromTpl"

    parents = (await logged_in_client.get(f"/api/tasks?project_id={new_proj['id']}")).json()
    assert len(parents) == 1
    assert parents[0]["title"] == "Parent"
    subs_html = (await logged_in_client.get(f"/htmx/tasks/{parents[0]['id']}/subtasks")).text
    assert "Child" in subs_html


async def test_delete_user_template(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Y"})).json()
    tpl = (
        await logged_in_client.post(f"/api/projects/{proj['id']}/save-as-template", json={})
    ).json()
    response = await logged_in_client.delete(f"/api/user-templates/{tpl['id']}")
    assert response.status_code == 204
    listing = (await logged_in_client.get("/api/user-templates")).json()
    assert all(t["id"] != tpl["id"] for t in listing)


async def test_save_unknown_project_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/projects/00000000-0000-0000-0000-000000000000/save-as-template",
        json={},
    )
    assert response.status_code == 404


async def test_instantiate_unknown_template_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/user-templates/00000000-0000-0000-0000-000000000000/instantiate",
        json={},
    )
    assert response.status_code == 404


async def test_save_button_appears_only_when_experiment_enabled(
    logged_in_client: AsyncClient,
) -> None:
    """The «Сохранить как шаблон» button is gated by the user_templates experiment."""
    proj = (await logged_in_client.post("/api/projects", json={"name": "MenuCheck"})).json()

    # OFF by default → button hidden.
    page_off = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    assert "Сохранить как шаблон" not in page_off.text

    # Toggle the experiment on → button appears.
    on = await logged_in_client.post(
        "/api/profile/experiments/user_templates", data={"enabled": "true"}
    )
    assert on.json()["enabled"] is True

    page_on = await logged_in_client.get(f"/app/projects/{proj['slug']}")
    assert "Сохранить как шаблон" in page_on.text
    assert "save-as-template" in page_on.text
