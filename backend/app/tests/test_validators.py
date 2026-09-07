"""Question-bank and exam-configuration validation rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import Difficulty, QuestionType
from app.services.validators import (
    OptionDraft,
    ValidationError,
    normalise_selection_rules,
    validate_exam_window,
    validate_question,
)


def _opts(*flags: bool) -> list[OptionDraft]:
    return [
        OptionDraft(text=f"Option {i}", is_correct=f, order_index=i) for i, f in enumerate(flags)
    ]


class TestMCQ:
    def test_exactly_one_correct_option_is_accepted(self):
        validate_question(
            question_type=QuestionType.MCQ,
            body="Which one?",
            marks=2,
            negative_marks=0.5,
            options=_opts(True, False, False, False),
            model_answer=None,
        )

    def test_two_correct_options_rejected(self):
        with pytest.raises(ValidationError, match="exactly one correct option"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=0,
                options=_opts(True, True, False, False),
                model_answer=None,
            )

    def test_no_correct_option_rejected(self):
        with pytest.raises(ValidationError, match="exactly one correct option"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=0,
                options=_opts(False, False),
                model_answer=None,
            )

    def test_single_option_rejected(self):
        with pytest.raises(ValidationError, match="at least 2 options"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=0,
                options=_opts(True),
                model_answer=None,
            )


class TestMultiSelect:
    def test_multiple_correct_accepted(self):
        validate_question(
            question_type=QuestionType.MULTI_SELECT,
            body="Select all",
            marks=3,
            negative_marks=1,
            options=_opts(True, True, False, False),
            model_answer=None,
        )

    def test_needs_at_least_one_correct(self):
        with pytest.raises(ValidationError, match="at least one correct"):
            validate_question(
                question_type=QuestionType.MULTI_SELECT,
                body="Select all",
                marks=3,
                negative_marks=0,
                options=_opts(False, False, False),
                model_answer=None,
            )

    def test_all_options_correct_rejected(self):
        with pytest.raises(ValidationError, match="every option marked correct"):
            validate_question(
                question_type=QuestionType.MULTI_SELECT,
                body="Select all",
                marks=3,
                negative_marks=0,
                options=_opts(True, True, True),
                model_answer=None,
            )


class TestSubjective:
    def test_short_answer_requires_model_answer(self):
        with pytest.raises(ValidationError, match="model answer"):
            validate_question(
                question_type=QuestionType.SHORT_ANSWER,
                body="Define normalisation",
                marks=5,
                negative_marks=0,
                options=[],
                model_answer=None,
            )

    def test_long_answer_with_model_answer_accepted(self):
        validate_question(
            question_type=QuestionType.LONG_ANSWER,
            body="Discuss CAP",
            marks=10,
            negative_marks=0,
            options=[],
            model_answer="A full discussion of consistency, availability and partitions.",
        )

    def test_subjective_must_not_have_options(self):
        with pytest.raises(ValidationError, match="must not define options"):
            validate_question(
                question_type=QuestionType.SHORT_ANSWER,
                body="Define normalisation",
                marks=5,
                negative_marks=0,
                options=_opts(True, False),
                model_answer="Some answer",
            )


class TestImageUpload:
    def test_requires_positive_marks(self):
        with pytest.raises(ValidationError, match="marks must be greater than 0"):
            validate_question(
                question_type=QuestionType.IMAGE_UPLOAD,
                body="Photograph your derivation",
                marks=0,
                negative_marks=0,
                options=[],
                model_answer=None,
            )

    def test_accepted_with_marks(self):
        validate_question(
            question_type=QuestionType.IMAGE_UPLOAD,
            body="Photograph your derivation",
            marks=8,
            negative_marks=0,
            options=[],
            model_answer=None,
        )


class TestMarks:
    def test_negative_marks_cannot_exceed_marks(self):
        with pytest.raises(ValidationError, match="cannot exceed"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=3,
                options=_opts(True, False),
                model_answer=None,
            )

    def test_negative_marks_cannot_be_negative(self):
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=-1,
                options=_opts(True, False),
                model_answer=None,
            )

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError, match="body cannot be empty"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="   ",
                marks=2,
                negative_marks=0,
                options=_opts(True, False),
                model_answer=None,
            )


class TestExamWindow:
    def test_valid_window(self):
        now = datetime.now(UTC)
        validate_exam_window(starts_at=now, ends_at=now + timedelta(hours=3), duration_minutes=60)

    def test_end_before_start_rejected(self):
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="end after it starts"):
            validate_exam_window(
                starts_at=now, ends_at=now - timedelta(hours=1), duration_minutes=30
            )

    def test_duration_longer_than_window_rejected(self):
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="exceeds the exam window"):
            validate_exam_window(
                starts_at=now, ends_at=now + timedelta(minutes=30), duration_minutes=60
            )


class TestSelectionRules:
    def test_normalises_valid_rules(self):
        rules = normalise_selection_rules(
            {"rules": [{"question_type": "mcq", "difficulty": "easy", "count": 5}]}
        )
        assert rules == [
            {
                "question_type": QuestionType.MCQ.value,
                "difficulty": Difficulty.EASY.value,
                "count": 5,
            }
        ]

    def test_null_difficulty_means_any(self):
        rules = normalise_selection_rules(
            {"rules": [{"question_type": "long_answer", "difficulty": None, "count": 1}]}
        )
        assert rules[0]["difficulty"] is None

    def test_empty_rules_rejected(self):
        with pytest.raises(ValidationError, match="at least one rule"):
            normalise_selection_rules({"rules": []})

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError, match="unknown question_type"):
            normalise_selection_rules({"rules": [{"question_type": "essay", "count": 1}]})

    def test_zero_count_rejected(self):
        with pytest.raises(ValidationError, match="positive integer count"):
            normalise_selection_rules({"rules": [{"question_type": "mcq", "count": 0}]})
