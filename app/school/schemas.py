"""Pydantic schemas for the school portal integration API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["school_mo", "mesh"]

PROVIDER_LABELS: dict[Provider, str] = {
    "school_mo": "Школьный портал МО",
    "mesh": "МЭШ (dnevnik.mos.ru)",
}


class IntegrationIn(BaseModel):
    """Form payload when the user saves credentials in /profile."""

    provider: Provider
    auth_token: str = Field(min_length=8, max_length=2048)
    # Portal student id (digits). Not secret; selects which child's diary.
    student_id: str | None = Field(default=None, max_length=32)
    target_project_id: UUID | None = None
    enabled: bool = True


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: Provider
    enabled: bool
    student_id: str | None
    target_project_id: UUID | None
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class SyncResult(BaseModel):
    """Returned after a /sync call — what got pulled (or why it didn't)."""

    ok: bool
    pulled: int = 0
    created: int = 0
    error: str | None = None
