"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.config import get_settings
from app.logging_setup import configure_logging

_settings = get_settings()
configure_logging(_settings.log_level)

app = FastAPI(title="SchoolTodo")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
