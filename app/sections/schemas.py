"""Pydantic schemas for section endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SectionCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=80)


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    position: int
    created_at: datetime
    updated_at: datetime


class SectionReorder(BaseModel):
    project_id: UUID
    ids: list[UUID] = Field(min_length=1)
