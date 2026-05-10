"""Pydantic schemas for complaint submission + admin views."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ComplaintIn(BaseModel):
    body: str = Field(min_length=3, max_length=4000)
    page_url: str | None = Field(default=None, max_length=500)
    viewport: str | None = Field(default=None, max_length=20)
    user_agent: str | None = Field(default=None, max_length=500)


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    body: str
    page_url: str | None
    viewport: str | None
    user_agent: str | None
    status: str
    priority: str
    admin_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class ComplaintAdminPatch(BaseModel):
    status: str | None = None
    priority: str | None = None
    admin_note: str | None = Field(default=None, max_length=2000)
