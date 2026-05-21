"""The g-prefix goto shortcuts must include the teams hubs (Команда / Назначено мне)."""

from httpx import AsyncClient


async def test_goto_team_and_assigned_shortcuts_present(logged_in_client: AsyncClient) -> None:
    # shortcuts.html is included on every /app page.
    body = (await logged_in_client.get("/app/today")).text
    # Key handlers route g+m → /app/team and g+e → /app/assigned (literal JS).
    assert "window.location.href = '/app/team'" in body
    assert "window.location.href = '/app/assigned'" in body
    # Overlay help (rendered) lists both kbd hints + labels.
    assert ">g m</kbd>" in body
    assert ">g e</kbd>" in body
    assert "Команда" in body
    assert "Назначено мне" in body
