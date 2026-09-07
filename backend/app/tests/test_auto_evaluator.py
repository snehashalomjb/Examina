"""Objective scoring, negative marking, and the multi-select partial-credit rule."""

from __future__ import annotations

import pytest

from app.db.models import QuestionType
from app.services.auto_evaluator import score_answer, score_objective
from app.tests.conftest import make_question, make_subject


@pytest.fixture
def mcq(db):
    subject = make_subject(db)
    return make_question(
        db, subject, qtype=QuestionType.MCQ, marks=2.0, negative=0.5, correct_indices=[0]
    )


@pytest.fixture
def multi(db):
    subject = make_subject(db)
    return make_question(
        db,
        subject,
        qtype=QuestionType.MULTI_SELECT,
        marks=4.0,
        negative=1.0,
        correct_indices=[0, 1],
        option_count=4,
    )


class TestMCQ:
    def test_correct_answer_earns_full_marks(self, mcq):
        correct = [str(o.id) for o in mcq.options if o.is_correct]
        outcome = score_objective(
            question=mcq, selected_option_ids=correct, max_marks=2.0, negative_marking=True
        )
        assert outcome.awarded == 2.0
        assert outcome.is_correct

    def test_wrong_answer_costs_the_penalty(self, mcq):
        wrong = [str(o.id) for o in mcq.options if not o.is_correct][:1]
        outcome = score_objective(
            question=mcq, selected_option_ids=wrong, max_marks=2.0, negative_marking=True
        )
        assert outcome.awarded == -0.5
        assert not outcome.is_correct

    def test_wrong_answer_costs_nothing_without_negative_marking(self, mcq):
        wrong = [str(o.id) for o in mcq.options if not o.is_correct][:1]
        outcome = score_objective(
            question=mcq, selected_option_ids=wrong, max_marks=2.0, negative_marking=False
        )
        assert outcome.awarded == 0.0

    def test_blank_never_attracts_a_penalty(self, mcq):
        outcome = score_objective(
            question=mcq, selected_option_ids=[], max_marks=2.0, negative_marking=True
        )
        assert outcome.awarded == 0.0
        assert not outcome.is_answered

    def test_multiple_selections_on_an_mcq_are_wrong(self, mcq):
        everything = [str(o.id) for o in mcq.options]
        outcome = score_objective(
            question=mcq, selected_option_ids=everything, max_marks=2.0, negative_marking=True
        )
        assert outcome.awarded == -0.5
        assert not outcome.is_correct


class TestMultiSelect:
    def test_exact_match_earns_full_marks(self, multi):
        correct = [str(o.id) for o in multi.options if o.is_correct]
        outcome = score_objective(
            question=multi, selected_option_ids=correct, max_marks=4.0, negative_marking=True
        )
        assert outcome.awarded == 4.0
        assert outcome.is_correct

    def test_partial_selection_is_zero_without_partial_credit(self, multi):
        one_correct = [str(o.id) for o in multi.options if o.is_correct][:1]
        outcome = score_objective(
            question=multi,
            selected_option_ids=one_correct,
            max_marks=4.0,
            negative_marking=True,
            partial_credit=False,
        )
        assert outcome.awarded == -1.0

    def test_partial_credit_scales_with_correct_selections(self, multi):
        one_correct = [str(o.id) for o in multi.options if o.is_correct][:1]
        outcome = score_objective(
            question=multi,
            selected_option_ids=one_correct,
            max_marks=4.0,
            negative_marking=True,
            partial_credit=True,
        )
        assert outcome.awarded == 2.0  # 1 of 2 correct options

    def test_any_wrong_selection_zeroes_partial_credit(self, multi):
        mixed = [str(o.id) for o in multi.options if o.is_correct][:1] + [
            str(o.id) for o in multi.options if not o.is_correct
        ][:1]
        outcome = score_objective(
            question=multi,
            selected_option_ids=mixed,
            max_marks=4.0,
            negative_marking=True,
            partial_credit=True,
        )
        assert outcome.awarded == -1.0

    def test_selecting_everything_is_not_a_pass(self, multi):
        everything = [str(o.id) for o in multi.options]
        outcome = score_objective(
            question=multi,
            selected_option_ids=everything,
            max_marks=4.0,
            negative_marking=True,
            partial_credit=True,
        )
        assert outcome.awarded == -1.0


def test_subjective_questions_are_not_auto_scorable(db):
    subject = make_subject(db)
    question = make_question(db, subject, qtype=QuestionType.LONG_ANSWER, marks=10)
    # score_answer is the engine's entry point, and the one that decides a question needs
    # a human. score_objective refuses it too, but for the narrower reason that it has no
    # options to score from.
    with pytest.raises(ValueError, match="not auto-scorable"):
        score_answer(
            question=question,
            selected_option_ids=None,
            text_answer="An essay.",
            max_marks=10,
            negative_marking=False,
        )
    with pytest.raises(ValueError, match="not scored from options"):
        score_objective(
            question=question, selected_option_ids=None, max_marks=10, negative_marking=False
        )
