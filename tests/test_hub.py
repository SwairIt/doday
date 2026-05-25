"""Studio hub at `/` — root landing showing all sibling projects."""

from httpx import AsyncClient


async def test_hub_renders_for_anon(client: AsyncClient) -> None:
    """Anonymous visitor — hub returns 200 with the 4 project cards."""
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 200
    body = response.text
    # Hub branding
    assert "Doday" in body
    assert "Мини-продукты" in body
    # All four project surfaces are linked from the hub.
    assert 'href="/doday"' in body  # Doday Tasks landing
    assert 'href="/lessio"' in body
    assert 'href="/game"' in body
    assert 'href="/taptower"' in body
    # Public navigation visible
    assert "/auth/login" in body
    assert "/auth/register" in body


async def test_hub_does_not_redirect_logged_in(logged_in_client: AsyncClient) -> None:
    """Hub stays accessible to logged-in users — it's a studio showcase, not the app shell."""
    response = await logged_in_client.get("/", follow_redirects=False)
    assert response.status_code == 200
    # Logged-in version shows the «К задачам →» CTA instead of login/register
    assert "К задачам" in response.text


async def test_hub_links_to_github_and_email(client: AsyncClient) -> None:
    """Footer carries the studio contacts."""
    body = (await client.get("/")).text
    assert "github.com/SwairIt/doday" in body
    assert "doday.support@gmail.com" in body
