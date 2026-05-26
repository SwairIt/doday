"""The task detail panel has a «Поделиться» button copying a ?task= deep-link.
The clipboard copy itself is Playwright-verified."""

from httpx import AsyncClient


async def test_detail_has_share_button(logged_in_client: AsyncClient) -> None:
    tid = (await logged_in_client.post("/api/tasks", json={"title": "ShareMe"})).json()["id"]
    html = (await logged_in_client.get(f"/doday/htmx/tasks/{tid}/detail")).text
    # Share button: deep-link + clipboard wiring present.
    assert f"?task={tid}" in html
    assert "navigator.clipboard" in html
    assert "Скопировать ссылку на задачу" in html
