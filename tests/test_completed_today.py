"""Test the 'Completed today' widget on /today."""

from httpx import AsyncClient


async def test_section_hidden_when_nothing_done(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/app/today")).text
    assert "Завершено сегодня" not in body


async def test_section_shows_after_completion(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Done now"})).json()
    await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/app/today")).text
    assert "Завершено сегодня" in body
    assert "Done now" in body


async def test_section_shows_count(logged_in_client: AsyncClient) -> None:
    for n in range(3):
        task = (await logged_in_client.post("/api/tasks", json={"title": f"T{n}"})).json()
        await logged_in_client.post(f"/htmx/tasks/{task['id']}/toggle")
    body = (await logged_in_client.get("/app/today")).text
    # the count is rendered inside a <span class="text-emerald-400">{N}</span>
    assert ">3<" in body or ">3</span" in body
