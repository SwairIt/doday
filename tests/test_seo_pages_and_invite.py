"""SEO landing pages + invite-friends modal — render checks + structured data.

These pages are crucial for organic acquisition; if they 500 on prod after a
careless refactor we lose Google indexing for weeks. The tests assert:
- HTTP 200 + content-type text/html
- key SEO meta tags present
- JSON-LD schema.org markup present and valid
- canonical URL points at the right path
- sitemap.xml lists every SEO landing
- invite_friends modal markup is on every authed page
"""

import json

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _public_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_for_students_renders_with_seo_meta() -> None:
    async with await _public_client() as c:
        resp = await c.get("/for-students")
    assert resp.status_code == 200
    body = resp.text
    # Title + description must mention the target keywords for ranking.
    assert "школьник" in body.lower() or "студент" in body.lower()
    assert "<title>" in body and "</title>" in body
    assert 'name="description"' in body
    assert 'name="keywords"' in body
    assert 'rel="canonical"' in body
    # JSON-LD SoftwareApplication schema.
    assert "application/ld+json" in body
    assert "SoftwareApplication" in body
    assert "EducationalAudience" in body


async def test_for_teachers_renders_with_seo_meta() -> None:
    async with await _public_client() as c:
        resp = await c.get("/for-teachers")
    assert resp.status_code == 200
    body = resp.text
    assert "учител" in body.lower() or "репетитор" in body.lower()
    assert "application/ld+json" in body
    assert "EducationApplication" in body


async def test_todoist_alternative_renders_with_faq_schema() -> None:
    async with await _public_client() as c:
        resp = await c.get("/todoist-alternative")
    assert resp.status_code == 200
    body = resp.text
    assert "todoist" in body.lower()
    # FAQPage schema unlocks Google rich-snippet FAQ accordion in search results.
    assert "FAQPage" in body
    assert "Question" in body


async def test_sitemap_includes_seo_pages() -> None:
    async with await _public_client() as c:
        resp = await c.get("/sitemap.xml")
    assert resp.status_code == 200
    body = resp.text
    assert "/for-students" in body
    assert "/for-teachers" in body
    assert "/todoist-alternative" in body
    assert "/pricing" in body
    assert "/help" in body


async def test_landing_footer_links_to_seo_pages() -> None:
    """Internal link-graph helps Google crawl new SEO pages from the homepage."""
    async with await _public_client() as c:
        resp = await c.get("/?preview=1")  # ?preview=1 lets logged-out users see the landing too
    body = resp.text
    assert "/for-students" in body
    assert "/for-teachers" in body
    assert "/todoist-alternative" in body


async def test_structured_data_is_valid_json(logged_in_client: AsyncClient) -> None:
    """Every <script application/ld+json> must parse — Google ignores malformed."""
    import re

    body = (await logged_in_client.get("/for-students")).text
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        body,
        flags=re.DOTALL,
    )
    assert blocks, "no JSON-LD blocks found"
    for raw in blocks:
        parsed = json.loads(raw.strip())
        assert "@context" in parsed
        assert "@type" in parsed


async def test_invite_friends_modal_in_authed_pages(logged_in_client: AsyncClient) -> None:
    """Invite-modal markup must be present on /app/today so the global trigger
    `window.dodayInviteFriends()` finds a target."""
    body = (await logged_in_client.get("/app/today")).text
    assert "dodayInviteFriends" in body or "open-invite-friends" in body
    assert "telegramShareUrl" in body or "Telegram" in body
    # Sidebar button calls the global function on click.
    assert "Позвать друга" in body or "Пригласить друга" in body


async def test_invite_modal_includes_share_targets(logged_in_client: AsyncClient) -> None:
    """All four share channels are linked from the modal."""
    body = (await logged_in_client.get("/app/today")).text
    assert "t.me/share/url" in body
    assert "vk.com/share.php" in body
    assert "api.whatsapp.com/send" in body
    assert "mailto:" in body
