"""FastAPI application entrypoint."""

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.auth.router import router as auth_router
from app.backup.router import router as backup_router
from app.comments.router import comments_router, task_comments_router
from app.config import get_settings
from app.custom_filters.router import router as custom_filters_router
from app.labels.router import router as labels_router
from app.labels.router import task_labels_router
from app.logging_setup import configure_logging
from app.pages.router import router as pages_router
from app.profile.router import router as profile_router
from app.projects.router import router as projects_router
from app.sections.router import router as sections_router
from app.tasks.router import reorder_router as tasks_reorder_router
from app.tasks.router import router as tasks_router
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
