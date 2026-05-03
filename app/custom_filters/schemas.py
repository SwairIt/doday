"""Pydantic schemas for custom filter endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DueWindow = Literal["today", "overdue", "upcoming-7", "no-date", "any"]
PriorityKey = Literal["p1", "p2", "p3", "p4"]


class FilterQuery(BaseModel):
    """Optional filter criteria. All fields combine with AND."""

    priorities: list[PriorityKey] | None = None
    project_ids: list[UUID] | None = None
    due_window: DueWindow | None = None
    has_text: str | None = Field(default=None, max_length=200)
    include_completed: bool = False


class CustomFilterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="violet", max_length=20)
    query: FilterQuery = Field(default_factory=FilterQuery)


class CustomFilterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=20)
    query: FilterQuery | None = None


class CustomFilterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str
    query: dict[str, object]
    position: int
    created_at: datetime
    updated_at: datetime
