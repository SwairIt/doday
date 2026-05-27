"""Tests for app.qa.schemas — anti-cheating server-side validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.qa.schemas import (
    ANSWER_MIN,
    EXPLANATION_MIN,
    AnswerCreate,
    QuestionCreate,
    ReportIn,
    VoteIn,
)


class TestQuestionCreate:
    def test_happy_path(self) -> None:
        q = QuestionCreate(
            subject_slug="algebra",
            grade=9,
            title="Как решить квадратное уравнение",
            body_md="Дано: x^2 + 2x - 3 = 0. Помогите разобрать.",
        )
        assert q.subject_slug == "algebra"
        assert q.grade == 9

    def test_grade_optional(self) -> None:
        q = QuestionCreate(
            subject_slug="russkij",
            title="Когда пишется н, а когда нн в прилагательных",
            body_md="Сформулируйте правило с примерами пожалуйста.",
        )
        assert q.grade is None

    def test_short_title_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            QuestionCreate(
                subject_slug="algebra",
                title="короткий",  # < 10 chars
                body_md="Достаточно длинное тело вопроса для прохождения min check.",
            )

    def test_short_body_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            QuestionCreate(
                subject_slug="algebra",
                title="Это длинный заголовок",
                body_md="мало",  # < 30 chars
            )

    def test_grade_out_of_range_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            QuestionCreate(
                subject_slug="algebra",
                grade=12,
                title="Это длинный заголовок",
                body_md="Достаточно длинное тело вопроса для прохождения min check.",
            )


class TestAnswerCreate:
    def test_happy_path(self) -> None:
        a = AnswerCreate(
            answer_md="x = -3 или x = 1",
            explanation_md=(
                "Дискриминант квадратного уравнения вычисляется по формуле "
                "D = b^2 - 4ac. В нашем случае a=1, b=2, c=-3, тогда "
                "D = 4 + 12 = 16. Корни ищем по формуле "
                "x = (-b ± sqrt(D)) / 2a = (-2 ± 4) / 2. "
                "Получаем два корня: x = 1 и x = -3."
            ),
        )
        assert "x = 1" in a.answer_md

    def test_short_answer_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AnswerCreate(
                answer_md="42",  # < ANSWER_MIN
                explanation_md="x" * (EXPLANATION_MIN + 10),
            )

    def test_short_explanation_rejected(self) -> None:
        """The critical anti-cheating check: explanation MUST be long enough."""
        with pytest.raises(PydanticValidationError):
            AnswerCreate(
                answer_md="x = 5",
                explanation_md="потому что",  # << EXPLANATION_MIN
            )

    def test_whitespace_padding_rejected(self) -> None:
        """Server-side validator rejects padded-with-spaces explanations."""
        padded = "потому" + " " * (EXPLANATION_MIN + 10)
        with pytest.raises(PydanticValidationError):
            AnswerCreate(answer_md="x = 5", explanation_md=padded)

    def test_minimum_lengths_documented(self) -> None:
        # Sanity check the spec constants line up with the schema validators.
        assert ANSWER_MIN >= 5
        assert EXPLANATION_MIN >= 100


class TestVoteIn:
    def test_valid_values(self) -> None:
        for v in (-1, 0, 1):
            for t in ("q", "a"):
                vote = VoteIn(target_type=t, target_id=1, value=v)
                assert vote.value == v

    def test_invalid_target_type(self) -> None:
        with pytest.raises(PydanticValidationError):
            VoteIn(target_type="x", target_id=1, value=1)

    def test_invalid_value(self) -> None:
        with pytest.raises(PydanticValidationError):
            VoteIn(target_type="q", target_id=1, value=2)


class TestReportIn:
    def test_valid(self) -> None:
        r = ReportIn(target_type="a", target_id=10, reason="spam")
        assert r.reason == "spam"

    def test_invalid_target_type(self) -> None:
        with pytest.raises(PydanticValidationError):
            ReportIn(target_type="zz", target_id=1, reason="spam")
