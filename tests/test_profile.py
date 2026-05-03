"""Tests for profile view + delete-account endpoint."""

from httpx import AsyncClient


async def test_profile_view_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/profile")
    assert response.status_code == 200
    assert "Профиль" in response.text
    assert "logged-in@example.com" in response.text
    assert "Удалить аккаунт" in response.text
    assert "Опасная зона" in response.text


async def test_profile_anon_blocked(client: AsyncClient) -> None:
    response = await client.get("/app/profile")
    assert response.status_code == 401


async def test_delete_account_cascades(
    logged_in_client: AsyncClient,
) -> None:
    # Create a project so cascade has something to chew on
    proj = await logged_in_client.post("/api/projects", json={"name": "Will be deleted"})
    assert proj.status_code == 201

    # Delete account
    response = await logged_in_client.post("/api/profile/delete", follow_redirects=False)
    assert response.status_code == 303
    assert "/?deleted=" in response.headers["location"]

    # Subsequent requests are anonymous (session was cleared)
    after = await logged_in_client.get("/api/projects")
    assert after.status_code == 401
