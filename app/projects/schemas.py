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
    is_favorite: bool | None = None
    description: str | None = Field(default=None, max_length=500)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    color: str
    position: int
    is_inbox: bool
    is_archived: bool
    is_favorite: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class ProjectReorder(BaseModel):
    ids: list[UUID] = Field(min_length=1)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    role: str
    joined_at: datetime


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invitee_email: str
    status: str
    expires_at: datetime


class InviteCreate(BaseModel):
    invitee_email: str = Field(min_length=1, max_length=255)


class IncomingInviteOut(BaseModel):
    """A pending invitation addressed to the current user (in-app banner)."""

    token: str
    project_name: str
