"""Pydantic schemas for habit endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(default="✅", min_length=1, max_length=8)
    color: str = Field(default="violet", max_length=20)


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    emoji: str | None = Field(default=None, min_length=1, max_length=8)
    color: str | None = Field(default=None, max_length=20)


class HabitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    emoji: str
    color: str
    archived_at: datetime | None
    created_at: datetime


class HabitWithStats(HabitOut):
    last_30: list[bool]  # length 30, index 0 = today, descending — true if checked
    current_streak: int
    longest_streak: int
    today_done: bool
