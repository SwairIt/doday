"""Pydantic schemas for label endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.projects.schemas import ProjectColor

LabelColor = ProjectColor  # same palette


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: LabelColor = "violet"


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: LabelColor | None = None


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    color: str
    created_at: datetime
    updated_at: datetime
