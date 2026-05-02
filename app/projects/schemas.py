"""Pydantic schemas for project HTTP endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProjectColor = Literal[
    "violet", "fuchsia", "sky", "emerald", "amber", "rose", "slate", "indigo", "teal"
]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: ProjectColor = "violet"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: ProjectColor | None = None
    is_archived: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    color: str
    position: int
    is_inbox: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
