"""Word counting, word-bound configuration, and the save-time ceiling."""

from __future__ import annotations

import pytest

from app.db.models import Difficulty, Question, QuestionType
from app.services.text_metrics import (
    WordCountError,
    check_answer_words,
    count_words,
    shortfall,
    validate_word_bounds,
)
from app.services.validators import OptionDraft, ValidationError, validate_question


def _question(
    question_type: QuestionType = QuestionType.LONG_ANSWER,
    *,
    min_words: int | None = None,
    max_words: int | None = None,
) -> Question:
    """A detached Question - these rules never touch the database."""
    return Question(
        question_type=question_type,
        difficulty=Difficulty.MEDIUM,
        body="Discuss.",
        marks=10,
        negative_marks=0,
        min_words=min_words,
        max_words=max_words,
    )


class TestCountWords:
    def test_empty_and_none_are_zero(self):
        assert count_words(None) == 0
        assert count_words("") == 0
        assert count_words("   \n\t ") == 0

    def test_plain_prose(self):
        assert count_words("the quick brown fox") == 4

    def test_punctuation_is_not_a_word(self):
        assert count_words("Yes! No? Maybe... -- ;") == 3

    def test_hyphenated_and_possessive_count_once(self):
        assert count_words("a well-formed candidate's answer") == 4

    def test_newlines_and_runs_of_space_collapse(self):
        assert count_words("one\n\ntwo   three\tfour") == 4

    def test_digits_and_units_count(self):
        assert count_words("3 mol dm-3 at 298 K") == 6


class TestConfiguringBounds:
    def test_bounds_on_a_written_question_are_allowed(self):
        validate_word_bounds(
            min_words=50, max_words=300, question_type=QuestionType.LONG_ANSWER
        )

    def test_min_above_max_is_rejected(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            validate_word_bounds(min_words=300, max_words=50)

    def test_negative_is_rejected(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            validate_word_bounds(min_words=-1, max_words=None)

    @pytest.mark.parametrize(
        "question_type",
        [QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.IMAGE_UPLOAD],
    )
    def test_bounds_are_meaningless_off_a_text_question(self, question_type):
        with pytest.raises(ValueError, match="do not take a word limit"):
            validate_word_bounds(min_words=None, max_words=200, question_type=question_type)

    def test_the_question_validator_enforces_the_same_rule(self):
        with pytest.raises(ValidationError, match="do not take a word limit"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="Which one?",
                marks=2,
                negative_marks=0,
                options=[
                    OptionDraft(text="Right", is_correct=True, order_index=0),
                    OptionDraft(text="Wrong", is_correct=False, order_index=1),
                ],
                model_answer=None,
                max_words=100,
            )

    def test_a_long_answer_may_carry_bounds_through_the_validator(self):
        validate_question(
            question_type=QuestionType.LONG_ANSWER,
            body="Discuss the trade-offs.",
            marks=10,
            negative_marks=0,
            options=None,
            model_answer="A model answer.",
            min_words=100,
            max_words=500,
        )


class TestSaveTimeCeiling:
    def test_an_answer_within_the_limit_returns_its_count(self):
        question = _question(max_words=5)
        assert check_answer_words(question, "one two three") == 3

    def test_an_answer_at_the_limit_is_accepted(self):
        question = _question(max_words=3)
        assert check_answer_words(question, "one two three") == 3

    def test_an_answer_over_the_limit_is_refused(self):
        question = _question(max_words=3)
        with pytest.raises(WordCountError, match="limit for this question is 3"):
            check_answer_words(question, "one two three four")

    def test_a_half_written_answer_is_never_refused_for_being_short(self):
        # Autosave fires while the candidate is still typing - the floor must not bite.
        question = _question(min_words=100, max_words=500)
        assert check_answer_words(question, "I would begin by") == 4

    def test_clearing_the_box_is_allowed(self):
        question = _question(min_words=100, max_words=500)
        assert check_answer_words(question, "") == 0

    def test_bounds_are_ignored_for_non_text_types(self):
        question = _question(QuestionType.IMAGE_UPLOAD, max_words=1)
        assert check_answer_words(question, "far more than one word here") == 6


class TestShortfall:
    def test_no_minimum_means_no_shortfall(self):
        assert shortfall(_question(), "three words here") == 0

    def test_an_under_length_answer_reports_the_gap(self):
        assert shortfall(_question(min_words=10), "three words here") == 7

    def test_a_long_enough_answer_reports_zero(self):
        assert shortfall(_question(min_words=2), "three words here") == 0

    def test_an_unanswered_question_is_not_under_length(self):
        # Nothing written is "unanswered", scored as such - not "13 words short".
        assert shortfall(_question(min_words=13), "") == 0
