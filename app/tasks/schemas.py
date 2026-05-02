"""Pydantic schemas for task HTTP endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.tasks.models import TaskPriority


class TaskCreate(BaseModel):
    project_id: UUID | None = None  # default → user's Inbox
    parent_task_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    due_at: datetime | None = None
    due_date_only: bool = True
    priority: TaskPriority = TaskPriority.P4


class TaskUpdate(BaseModel):
    project_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    due_at: datetime | None = None
    due_date_only: bool | None = None
    priority: TaskPriority | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    parent_task_id: UUID | None
    title: str
    description: str | None
    due_at: datetime | None
    due_date_only: bool
    priority: TaskPriority
    is_completed: bool
    completed_at: datetime | None
    position: int
    created_at: datetime
    updated_at: datetime


class TaskReorder(BaseModel):
    ids: list[UUID] = Field(min_length=1)
