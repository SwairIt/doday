"""FastAPI application entrypoint."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from app.achievements.router import router as achievements_router
from app.auth.router import router as auth_router
from app.backup.router import router as backup_router
from app.billing.router import router as billing_router
from app.calendar_feed.router import router as calendar_feed_router
from app.calendar_feed.router import token_router as calendar_token_router
from app.comments.router import comments_router, task_comments_router
from app.company.router import router as company_router
from app.config import get_settings
from app.custom_filters.router import router as custom_filters_router
from app.digest.router import router as digest_router
from app.habits.router import router as habits_router
from app.help.router import router as help_router
from app.labels.router import router as labels_router
from app.labels.router import task_labels_router
from app.links.router import graph_router as links_graph_router
from app.links.router import router as links_router
from app.logging_setup import configure_logging
from app.mood.router import router as mood_router
from app.pages.router import router as pages_router
from app.profile.router import router as profile_router
from app.projects.router import router as projects_router
from app.school.router import router as school_router
from app.sections.router import router as sections_router
from app.stats.router import router as stats_router
from app.tasks.router import reorder_router as tasks_reorder_router
from app.tasks.router import router as tasks_router
from app.time_tracking.router import router as time_tracking_router
from app.user_templates.router import router as user_templates_router
from app.user_templates.router import save_router as save_as_template_router
from app.views.htmx import router as htmx_router
from app.views.router import router as views_router

_settings = get_settings()
configure_logging(_settings.log_level)

app = FastAPI(title="SchoolTodo")

_is_prod = _settings.app_env == "prod"

app.add_middleware(
    SessionMiddleware,
    secret_key=_settings.app_secret_key,
    same_site="lax",
    https_only=_is_prod,  # require Secure cookie in production (HTTPS-only)
    # httpOnly is True by default in Starlette's SessionMiddleware
)


# Defence-in-depth: nginx adds these too, but if someone hits uvicorn directly
# (or runs without nginx for a quick test), we still ship safe defaults.
@app.middleware("http")
async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Expose Yandex.Metrika counter ID to all templates via request.state.
    # Empty string in dev → base.html silently skips the <script> block.
    request.state.ya_metrika_id = _settings.ya_metrika_id
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if _is_prod:
        # 6 months HSTS once HTTPS is wired up; nginx will be terminating TLS.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=15552000; includeSubDomains"
        )
    return response


app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(tasks_reorder_router)
app.include_router(labels_router)
app.include_router(task_labels_router)
app.include_router(views_router)
app.include_router(htmx_router)
app.include_router(profile_router)
app.include_router(sections_router)
app.include_router(backup_router)
app.include_router(task_comments_router)
app.include_router(comments_router)
app.include_router(custom_filters_router)
app.include_router(user_templates_router)
app.include_router(save_as_template_router)
app.include_router(billing_router)
app.include_router(help_router)
app.include_router(school_router)
app.include_router(company_router)
app.include_router(stats_router)
app.include_router(calendar_feed_router)
app.include_router(calendar_token_router)
app.include_router(habits_router)
app.include_router(time_tracking_router)
app.include_router(mood_router)
app.include_router(achievements_router)
app.include_router(links_router)
app.include_router(links_graph_router)
app.include_router(digest_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    """Allow indexing of marketing pages, disallow the logged-in app shell."""
    body = (
        "User-agent: *\n"
        "Disallow: /app/\n"
        "Disallow: /api/\n"
        "Disallow: /htmx/\n"
        "Disallow: /auth/\n"
        f"Sitemap: {_settings.app_base_url.rstrip('/')}/sitemap.xml\n"
    )
    return PlainTextResponse(body)


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    """Static sitemap for the public marketing pages + every help article."""
    from app.help.articles import ARTICLES

    base = _settings.app_base_url.rstrip("/")
    static_paths = ["/", "/privacy", "/help"]
    article_paths = [f"/help/{a['slug']}" for a in ARTICLES]
    items = "".join(
        f"<url><loc>{base}{p}</loc><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if p == '/' else '0.7'}</priority></url>"
        for p in static_paths + article_paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return Response(content=body, media_type="application/xml")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Inline SVG favicon — same gradient D as the PWA icon."""
    return Response(content=_PWA_ICON_SVG, media_type="image/svg+xml")


_OG_IMAGE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">'
    "<defs>"
    '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#0d0820"/>'
    '<stop offset="1" stop-color="#2e1065"/>'
    "</linearGradient>"
    '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#7c3aed"/>'
    '<stop offset="1" stop-color="#d946ef"/>'
    "</linearGradient>"
    '<radialGradient id="glow" cx="50%" cy="50%" r="50%">'
    '<stop offset="0%" stop-color="#a78bfa" stop-opacity="0.5"/>'
    '<stop offset="100%" stop-color="#a78bfa" stop-opacity="0"/>'
    "</radialGradient>"
    "</defs>"
    '<rect width="1200" height="630" fill="url(#bg)"/>'
    '<circle cx="950" cy="200" r="320" fill="url(#glow)"/>'
    '<rect x="80" y="225" width="180" height="180" rx="40" fill="url(#g)"/>'
    '<text x="170" y="345" text-anchor="middle" '
    'font-family="Inter,Arial,sans-serif" font-weight="800" '
    'font-size="120" fill="white">D</text>'
    '<text x="300" y="290" font-family="Inter,Arial,sans-serif" '
    'font-weight="800" font-size="84" fill="white">Doday</text>'
    '<text x="300" y="360" font-family="Inter,Arial,sans-serif" '
    'font-weight="500" font-size="36" fill="#a78bfa">'
    "Бесплатный туду-лист, который не мешает</text>"
    '<text x="300" y="420" font-family="Inter,Arial,sans-serif" '
    'font-weight="400" font-size="26" fill="#ddd6fe">'
    "Проекты · Календарь · Граф связей · Помодоро · Привычки</text>"
    '<text x="80" y="580" font-family="Inter,Arial,sans-serif" '
    'font-weight="600" font-size="28" fill="#a78bfa">getdoday.ru</text>'
    "</svg>"
)


@app.get("/og.svg", include_in_schema=False)
async def og_image() -> Response:
    """OpenGraph preview image — 1200x630 brand card for social sharing."""
    return Response(
        content=_OG_IMAGE_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# PWA endpoints — manifest + service worker. Inlined so we don't need a
# separate static directory or build step. Icon is rendered as inline SVG
# data-URL inside the manifest to avoid extra HTTP round-trips.
# ---------------------------------------------------------------------------

_PWA_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#7c3aed"/><stop offset="1" stop-color="#d946ef"/>'
    "</linearGradient></defs>"
    '<rect width="192" height="192" rx="40" fill="url(#g)"/>'
    '<text x="50%" y="56%" text-anchor="middle" dominant-baseline="middle" '
    'font-family="Inter,Arial,sans-serif" font-weight="800" font-size="120" fill="white">D</text>'
    "</svg>"
)


@app.get("/manifest.webmanifest")
async def pwa_manifest() -> Response:
    import json
    from urllib.parse import quote

    icon_url = "data:image/svg+xml;utf8," + quote(_PWA_ICON_SVG)
    body = json.dumps(
        {
            "name": "Doday — todo для всех",
            "short_name": "Doday",
            "description": "Бесплатный туду-лист для школьников, компаний и личных дел",
            "lang": "ru",
            "start_url": "/app/today",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#0d0820",
            "theme_color": "#7c3aed",
            "icons": [
                {"src": icon_url, "sizes": "192x192", "type": "image/svg+xml", "purpose": "any"},
                {
                    "src": icon_url,
                    "sizes": "512x512",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                },
            ],
        },
        ensure_ascii=False,
    )
    return Response(content=body, media_type="application/manifest+json")


@app.get("/service-worker.js")
async def pwa_service_worker() -> Response:
    body = """// Doday service worker — minimal cache-first for the app shell, network for everything else.
const CACHE = 'doday-shell-v1';
const SHELL = ['/app/today', '/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => null)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  // Never cache the API.
  if (new URL(req.url).pathname.startsWith('/api/')) return;
  e.respondWith(
    fetch(req).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(req, copy)).catch(() => null);
      return r;
    }).catch(() => caches.match(req).then(c => c || new Response('Offline', {status: 503})))
  );
});
"""
    return Response(content=body, media_type="application/javascript")
