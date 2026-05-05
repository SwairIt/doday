"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.responses import Response
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
from app.habits.router import router as habits_router
from app.help.router import router as help_router
from app.labels.router import router as labels_router
from app.labels.router import task_labels_router
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
