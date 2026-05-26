"""Tests for profile view + delete-account endpoint."""

from httpx import AsyncClient


async def test_profile_view_renders(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/doday/app/settings")
    assert response.status_code == 200
    assert "Настройки" in response.text
    assert "logged-in@example.com" in response.text
    assert "Удалить аккаунт" in response.text
    assert "Опасная зона" in response.text


async def test_profile_anon_blocked(client: AsyncClient) -> None:
    # /doday/app/profile is now a redirect; the settings page behind it requires auth
    response = await client.get("/doday/app/settings", follow_redirects=False)
    assert response.status_code == 401


async def test_change_password_success(logged_in_client: AsyncClient) -> None:
    """Changing the password succeeds with the correct current password."""
    r = await logged_in_client.post(
        "/api/profile/password",
        data={"current_password": "strongpass123", "new_password": "newpass987abc"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_change_password_wrong_current(logged_in_client: AsyncClient) -> None:
    """Changing the password fails when the current password is wrong."""
    r = await logged_in_client.post(
        "/api/profile/password",
        data={"current_password": "WRONG", "new_password": "newpass987abc"},
    )
    assert r.status_code == 400
    assert "невер" in r.json()["detail"].lower()


async def test_change_password_too_short(logged_in_client: AsyncClient) -> None:
    """Rejects new passwords shorter than 8 characters."""
    r = await logged_in_client.post(
        "/api/profile/password",
        data={"current_password": "strongpass123", "new_password": "short"},
    )
    assert r.status_code == 422


async def test_change_password_persists_for_next_login(
    logged_in_client: AsyncClient,
) -> None:
    """After changing the password, login with the new password succeeds and the old fails."""
    await logged_in_client.post(
        "/api/profile/password",
        data={"current_password": "strongpass123", "new_password": "newpass987abc"},
    )
    await logged_in_client.post("/auth/logout")
    bad = await logged_in_client.post(
        "/auth/login",
        data={"email": "logged-in@example.com", "password": "strongpass123"},
    )
    assert bad.status_code != 303
    good = await logged_in_client.post(
        "/auth/login",
        data={"email": "logged-in@example.com", "password": "newpass987abc"},
    )
    assert good.status_code == 303


async def test_change_password_anon_blocked(client: AsyncClient) -> None:
    r = await client.post(
        "/api/profile/password",
        data={"current_password": "x", "new_password": "y"},
    )
    assert r.status_code == 401


async def test_profile_renders_password_form(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/settings")).text
    assert "Сменить пароль" in body
    assert "/api/profile/password" in body


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
