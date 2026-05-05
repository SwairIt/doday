"""Pydantic schemas for task-link endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LinkIn(BaseModel):
    """Body for POST /api/tasks/{id}/links."""

    target_task_id: UUID
    note: str | None = Field(default=None, max_length=200)


class LinkedTaskOut(BaseModel):
    """A task referenced via a link, with the minimum we need to render a chip."""

    model_config = ConfigDict(from_attributes=True)

    link_id: UUID
    task_id: UUID
    title: str
    project_id: UUID
    project_name: str
    is_completed: bool
    direction: str  # "outgoing" | "incoming"
    note: str | None
    created_at: datetime
