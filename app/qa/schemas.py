"""Pydantic v2 schemas for the Razbery feature.

Server-side validation is the source of truth — client validation is purely
UX. Anti-cheating minimum lengths enforced here so a curl-attack can't bypass
the two-field structure.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Minimum lengths — also referenced by templates for the live counter
TITLE_MIN = 10
TITLE_MAX = 250
BODY_MIN = 30
ANSWER_MIN = 10
EXPLANATION_MIN = 150
BIO_MAX = 280
DISPLAY_NAME_MIN = 2
DISPLAY_NAME_MAX = 50


class QuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject_slug: str = Field(min_length=2, max_length=50)
    grade: int | None = Field(default=None, ge=5, le=11)
    title: str = Field(min_length=TITLE_MIN, max_length=TITLE_MAX)
    body_md: str = Field(min_length=BODY_MIN)


class QuestionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=TITLE_MIN, max_length=TITLE_MAX)
    body_md: str | None = Field(default=None, min_length=BODY_MIN)
    grade: int | None = Field(default=None, ge=5, le=11)


class AnswerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer_md: str = Field(min_length=ANSWER_MIN)
    explanation_md: str = Field(min_length=EXPLANATION_MIN)

    @field_validator("explanation_md")
    @classmethod
    def explanation_must_be_substantive(cls, v: str) -> str:
        """Reject explanations that are just whitespace-padded short text."""
        if len(v.strip()) < EXPLANATION_MIN:
            raise ValueError(f"объяснение должно быть не короче {EXPLANATION_MIN} символов")
        return v


class AnswerUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer_md: str | None = Field(default=None, min_length=ANSWER_MIN)
    explanation_md: str | None = Field(default=None, min_length=EXPLANATION_MIN)


class VoteIn(BaseModel):
    target_type: str = Field(pattern="^[qa]$")
    target_id: int = Field(ge=1)
    value: int = Field(ge=-1, le=1)  # -1, 0 (un-vote), +1


class ReportIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_type: str = Field(pattern="^[qa]$")
    target_id: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=50)
    comment: str | None = Field(default=None, max_length=500)


class UserStatsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str | None = Field(
        default=None, min_length=DISPLAY_NAME_MIN, max_length=DISPLAY_NAME_MAX
    )
    bio: str | None = Field(default=None, max_length=BIO_MAX)
    avatar_emoji: str | None = Field(default=None, min_length=1, max_length=8)


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: UUID | None
    subject_id: int
    grade: int | None
    title: str
    slug: str
    body_md: str
    body_html: str
    score: int
    answer_count: int
    view_count: int
    accepted_answer_id: int | None
    is_seed: bool
    is_hidden: bool
    created_at: datetime
    updated_at: datetime


class AnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    author_id: UUID | None
    answer_md: str
    answer_html: str
    explanation_md: str
    explanation_html: str
    score: int
    is_accepted: bool
    is_seed: bool
    is_hidden: bool
    created_at: datetime
    updated_at: datetime


VALID_REPORT_REASONS = {"spam", "offtopic", "wrong_answer", "abuse", "cheating_request"}
