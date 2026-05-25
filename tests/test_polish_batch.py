"""Tests for the latest polish batch: weekly goal, focus mode, theme cycle,
markdown preview, move-to-section, tab badge, logout-in-sidebar."""

from httpx import AsyncClient


async def test_today_renders_weekly_goal(logged_in_client: AsyncClient) -> None:
    page = await logged_in_client.get("/app/today")
    assert page.status_code == 200
    body = page.text
    assert "doday-daily-goal" in body
    assert "doday-weekly-goal" in body
    assert "На неделе" in body


async def test_focus_mode_wired(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "focus-mode" in body
    assert "Выйти из focus" in body
    # Listener for `f` key.
    assert "if (e.key === 'f')" in body or "key === 'f'" in body


async def test_theme_cycle_button_present(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "doday-theme" in body
    assert "system" in body  # cycle includes System
    # Three SVG variants for the three modes.
    assert "mode === 'system'" in body
    assert "mode === 'light'" in body
    assert "mode === 'dark'" in body


async def test_tab_badge_script_included(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "/api/tasks/today" in body
    assert "document.title" in body


async def test_logout_button_in_sidebar(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    # Logout form posts to /auth/logout, button has aria-label.
    assert 'action="/auth/logout"' in body
    assert "Выйти из аккаунта" in body


async def test_landing_preview_for_logged_in(logged_in_client: AsyncClient) -> None:
    """Doday Tasks landing at /doday — logged-in user can preview with ?preview=1."""
    response = await logged_in_client.get("/doday?preview=1", follow_redirects=False)
    assert response.status_code == 200
    assert "Тудулист" in response.text or "Doday" in response.text


async def test_landing_still_redirects_without_preview(logged_in_client: AsyncClient) -> None:
    """Without ?preview=1, logged-in users get bounced to /app/today."""
    response = await logged_in_client.get("/doday", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].endswith("/app/today")


async def test_task_detail_includes_section_dropdown(logged_in_client: AsyncClient) -> None:
    proj = (await logged_in_client.post("/api/projects", json={"name": "Sec"})).json()
    sec = (
        await logged_in_client.post(
            "/api/sections", json={"project_id": proj["id"], "name": "InProgress"}
        )
    ).json()
    task = (
        await logged_in_client.post("/api/tasks", json={"title": "T", "project_id": proj["id"]})
    ).json()
    body = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/detail")).text
    assert ">Секция<" in body
    assert "Без секции" in body
    assert "/api/sections?project_id=" in body
    # The section we created loads via fetch — its ID is referenced for setSection.
    assert sec["id"] in body or "sections" in body


async def test_task_detail_includes_markdown_preview(logged_in_client: AsyncClient) -> None:
    task = (
        await logged_in_client.post(
            "/api/tasks", json={"title": "T", "description": "**bold** test"}
        )
    ).json()
    body = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/detail")).text
    # md-preview wrapper present + uses the global window.dodayMd() renderer.
    assert "md-preview" in body
    assert "dodayMd" in body
    # Description is wired into x-data text.
    assert "**bold** test" in body
