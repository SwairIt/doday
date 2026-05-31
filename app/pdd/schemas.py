"""Pydantic v2 DTOs for the Doday PDD JSON API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AttemptSource = Literal["practice", "exam", "trainer"]


class AttemptIn(BaseModel):
    """Body of POST /api/pdd/attempt — one answered question."""

    question_id: int
    chosen_position: int = Field(ge=1)
    source: AttemptSource = "practice"


class AttemptOut(BaseModel):
    """Result of recording an attempt — enough for the client to reveal."""

    is_correct: bool
    correct_position: int
    explanation: str


class ExamAnswerIn(BaseModel):
    """One answered question in an exam run."""

    question_id: int
    chosen_position: int = Field(ge=1)


class ExamSaveIn(BaseModel):
    """Body of POST /api/pdd/exam/save — a finished simulator run (Pro)."""

    answers: list[ExamAnswerIn] = Field(min_length=1, max_length=40)
