"""Tests for production hardening: security headers + robots/sitemap."""

from httpx import AsyncClient


async def test_security_headers_on_response(client: AsyncClient) -> None:
    """Defence-in-depth headers ship on every HTTP response, even unauthed."""
    r = await client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "same-origin"
    assert "Permissions-Policy" in r.headers or "permissions-policy" in r.headers


async def test_robots_txt_disallows_app_paths(client: AsyncClient) -> None:
    r = await client.get("/robots.txt")
    assert r.status_code == 200
    body = r.text
    assert "User-agent: *" in body
    for path in ("/app/", "/api/", "/htmx/", "/auth/"):
        assert f"Disallow: {path}" in body
    assert "Sitemap:" in body


async def test_sitemap_xml_exposes_marketing_pages(client: AsyncClient) -> None:
    r = await client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")
    body = r.text
    assert "<urlset" in body
    # Marketing pages should be in there; app shell paths must NOT
    assert "/privacy" in body
    assert "/app/" not in body
