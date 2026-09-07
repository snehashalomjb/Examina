"""The five question types added for the two exam modes.

Covers the spec contract (what an examiner may configure), the validation rules that stop
an unanswerable question being saved, and the scoring behaviour for the types the
platform marks without a human.
"""

from __future__ import annotations

import pytest

from app.db.models import QuestionType
from app.services.auto_evaluator import parse_number, score_answer, score_response
from app.services.question_spec import (
    SpecError,
    load_spec,
    validate_spec,
)
from app.services.validators import OptionDraft, ValidationError, validate_question
from app.tests.conftest import make_question, make_subject


def _opts(*flags: bool) -> list[OptionDraft]:
    return [
        OptionDraft(text=f"Option {i}", is_correct=f, order_index=i) for i, f in enumerate(flags)
    ]


# ============================================================ spec validation
class TestNumericalSpec:
    def test_a_minimal_spec_is_accepted(self):
        stored = validate_spec(QuestionType.NUMERICAL, {"answer": 9.81})
        assert stored["answer"] == 9.81
        assert stored["tolerance"] == 0.0

    def test_tolerances_round_trip(self):
        stored = validate_spec(
            QuestionType.NUMERICAL,
            {"answer": 100, "tolerance": 0.5, "relative_tolerance": 0.01, "unit": "m/s"},
        )
        assert stored["relative_tolerance"] == 0.01
        assert stored["unit"] == "m/s"

    def test_a_missing_answer_is_refused(self):
        with pytest.raises(SpecError, match="answer"):
            validate_spec(QuestionType.NUMERICAL, {"tolerance": 0.5})

    def test_a_negative_tolerance_is_refused(self):
        with pytest.raises(SpecError, match="tolerance"):
            validate_spec(QuestionType.NUMERICAL, {"answer": 1, "tolerance": -1})

    def test_an_unknown_key_is_refused(self):
        # A typo that is silently ignored reads as the platform marking wrongly.
        with pytest.raises(SpecError):
            validate_spec(QuestionType.NUMERICAL, {"answer": 1, "tolerence": 0.5})

    def test_a_numerical_question_cannot_be_saved_without_one(self):
        with pytest.raises(SpecError, match="need a spec"):
            validate_spec(QuestionType.NUMERICAL, None)


class TestFillBlankSpec:
    def test_accepted_answers_round_trip(self):
        stored = validate_spec(
            QuestionType.FILL_BLANK, {"accepted_answers": ["water", "H2O"]}
        )
        assert stored["accepted_answers"] == ["water", "H2O"]
        assert stored["case_sensitive"] is False
        assert stored["normalise_whitespace"] is True

    def test_an_empty_list_is_refused(self):
        with pytest.raises(SpecError):
            validate_spec(QuestionType.FILL_BLANK, {"accepted_answers": []})

    def test_all_blank_answers_are_refused(self):
        with pytest.raises(SpecError, match="blank"):
            validate_spec(QuestionType.FILL_BLANK, {"accepted_answers": ["   ", ""]})


class TestCodingSpec:
    def _valid(self) -> dict:
        return {
            "languages": ["python", "java"],
            "input_format": "A single integer n.",
            "output_format": "The nth Fibonacci number.",
            "constraints": "1 <= n <= 40",
            "sample_cases": [{"input": "5", "output": "5"}],
        }

    def test_a_complete_spec_is_accepted(self):
        stored = validate_spec(QuestionType.CODING, self._valid())
        assert stored["languages"] == ["python", "java"]
        assert len(stored["sample_cases"]) == 1

    @pytest.mark.parametrize(
        "missing", ["input_format", "output_format", "constraints", "sample_cases", "languages"]
    )
    def test_every_required_part_is_enforced(self, missing):
        payload = self._valid()
        del payload[missing]
        with pytest.raises(SpecError, match=missing):
            validate_spec(QuestionType.CODING, payload)

    def test_an_unsupported_language_is_refused(self):
        payload = self._valid()
        payload["languages"] = ["cobol"]
        with pytest.raises(SpecError):
            validate_spec(QuestionType.CODING, payload)

    def test_the_default_language_must_be_offered(self):
        payload = self._valid()
        payload["default_language"] = "cpp"
        with pytest.raises(SpecError, match="one of the offered languages"):
            validate_spec(QuestionType.CODING, payload)

    def test_starter_code_must_match_the_offered_languages(self):
        payload = self._valid()
        payload["starter_code"] = {"cpp": "int main(){}"}
        with pytest.raises(SpecError, match="not offered"):
            validate_spec(QuestionType.CODING, payload)


class TestOptionalAndForbiddenSpecs:
    def test_a_passage_gets_defaults_when_none_is_given(self):
        stored = validate_spec(QuestionType.PASSAGE, None)
        assert stored["sticky"] is True

    def test_true_false_labels_are_configurable(self):
        stored = validate_spec(
            QuestionType.TRUE_FALSE, {"true_label": "Yes", "false_label": "No"}
        )
        assert stored["true_label"] == "Yes"

    def test_an_mcq_takes_no_spec(self):
        assert validate_spec(QuestionType.MCQ, None) is None

    def test_a_spec_on_an_mcq_is_refused(self):
        with pytest.raises(SpecError, match="do not take a spec"):
            validate_spec(QuestionType.MCQ, {"answer": 1})

    def test_a_malformed_stored_spec_does_not_raise_on_read(self):
        # A row written before a field existed must still score rather than break an exam.
        assert load_spec(QuestionType.NUMERICAL, {"nonsense": True}) is None


# ============================================================= question rules
class TestTrueFalseValidation:
    def test_two_options_one_correct_is_accepted(self):
        validate_question(
            question_type=QuestionType.TRUE_FALSE,
            body="The Earth orbits the Sun.",
            marks=1,
            negative_marks=0,
            options=_opts(True, False),
            model_answer=None,
        )

    def test_three_options_are_refused(self):
        with pytest.raises(ValidationError, match="exactly 2 options"):
            validate_question(
                question_type=QuestionType.TRUE_FALSE,
                body="Pick one.",
                marks=1,
                negative_marks=0,
                options=_opts(True, False, False),
                model_answer=None,
            )

    def test_two_correct_options_are_refused(self):
        with pytest.raises(ValidationError, match="exactly one correct option"):
            validate_question(
                question_type=QuestionType.TRUE_FALSE,
                body="Pick one.",
                marks=1,
                negative_marks=0,
                options=_opts(True, True),
                model_answer=None,
            )


class TestPassageValidation:
    def test_a_passage_carries_no_marks(self):
        with pytest.raises(ValidationError, match="carries no marks"):
            validate_question(
                question_type=QuestionType.PASSAGE,
                body="Read the following extract...",
                marks=5,
                negative_marks=0,
                options=None,
                model_answer=None,
            )

    def test_a_zero_mark_passage_is_accepted(self):
        stored = validate_question(
            question_type=QuestionType.PASSAGE,
            body="Read the following extract...",
            marks=0,
            negative_marks=0,
            options=None,
            model_answer=None,
        )
        assert stored["kind"] == "passage"


class TestImageBackedQuestions:
    def test_a_body_may_be_empty_when_an_image_carries_the_question(self):
        validate_question(
            question_type=QuestionType.MCQ,
            body="",
            marks=1,
            negative_marks=0,
            options=_opts(True, False),
            model_answer=None,
            image_key="questions/abc/figure.png",
        )

    def test_an_empty_body_with_no_image_is_still_refused(self):
        with pytest.raises(ValidationError, match="body cannot be empty"):
            validate_question(
                question_type=QuestionType.MCQ,
                body="   ",
                marks=1,
                negative_marks=0,
                options=_opts(True, False),
                model_answer=None,
            )


class TestSpecFlowsThroughTheValidator:
    def test_a_coding_question_without_a_spec_is_refused(self):
        with pytest.raises(ValidationError, match="need a spec"):
            validate_question(
                question_type=QuestionType.CODING,
                body="Write a function.",
                marks=10,
                negative_marks=0,
                options=None,
                model_answer=None,
            )

    def test_the_validator_returns_the_normalised_spec(self):
        stored = validate_question(
            question_type=QuestionType.NUMERICAL,
            body="What is g?",
            marks=2,
            negative_marks=0,
            options=None,
            model_answer=None,
            spec={"answer": 9.81, "tolerance": 0.01},
        )
        # Defaults filled in, so what gets saved is complete rather than partial.
        assert stored == {
            "kind": "numerical",
            "answer": 9.81,
            "tolerance": 0.01,
            "relative_tolerance": None,
            "unit": None,
        }


# =================================================================== scoring
class TestParseNumber:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("42", 42.0),
            ("  3.14 ", 3.14),
            ("-2.5", -2.5),
            ("1e-3", 0.001),
            ("1,234.5", 1234.5),
            ("−7", -7.0),  # unicode minus, as pasted from a document
            (".5", 0.5),
        ],
    )
    def test_numbers_people_actually_type(self, raw, expected):
        assert parse_number(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", ["", "   ", None, "about 5", "5 m/s", "five", "1/2"])
    def test_non_numbers_are_rejected(self, raw):
        assert parse_number(raw) is None


class TestNumericalScoring:
    @pytest.fixture
    def question(self, db):
        return make_question(
            db,
            make_subject(db),
            qtype=QuestionType.NUMERICAL,
            marks=3.0,
            negative=1.0,
            spec={"kind": "numerical", "answer": 9.81, "tolerance": 0.05},
        )

    def test_an_exact_answer_earns_full_marks(self, question):
        outcome = score_response(
            question=question, text_answer="9.81", max_marks=3.0, negative_marking=True
        )
        assert outcome.awarded == 3.0
        assert outcome.is_correct

    def test_an_answer_inside_the_tolerance_is_correct(self, question):
        outcome = score_response(
            question=question, text_answer="9.8", max_marks=3.0, negative_marking=True
        )
        assert outcome.is_correct

    def test_an_answer_outside_the_tolerance_costs_the_penalty(self, question):
        outcome = score_response(
            question=question, text_answer="9.5", max_marks=3.0, negative_marking=True
        )
        assert outcome.awarded == -1.0
        assert not outcome.is_correct

    def test_a_blank_is_unanswered_and_never_penalised(self, question):
        outcome = score_response(
            question=question, text_answer="   ", max_marks=3.0, negative_marking=True
        )
        assert outcome.awarded == 0.0
        assert not outcome.is_answered

    def test_unparseable_text_counts_as_an_attempt(self, question):
        # "about ten" is a wrong answer, not an unanswered question.
        outcome = score_response(
            question=question, text_answer="about ten", max_marks=3.0, negative_marking=True
        )
        assert outcome.is_answered
        assert outcome.awarded == -1.0

    def test_relative_tolerance_widens_the_band(self, db):
        question = make_question(
            db,
            make_subject(db),
            qtype=QuestionType.NUMERICAL,
            marks=2.0,
            spec={"kind": "numerical", "answer": 1000.0, "relative_tolerance": 0.01},
        )
        assert score_response(
            question=question, text_answer="1009", max_marks=2.0, negative_marking=False
        ).is_correct
        assert not score_response(
            question=question, text_answer="1011", max_marks=2.0, negative_marking=False
        ).is_correct

    def test_a_question_with_no_usable_spec_refuses_to_guess(self, db):
        question = make_question(
            db, make_subject(db), qtype=QuestionType.NUMERICAL, marks=2.0, spec=None
        )
        with pytest.raises(ValueError, match="no usable spec"):
            score_response(
                question=question, text_answer="1", max_marks=2.0, negative_marking=False
            )


class TestFillBlankScoring:
    @pytest.fixture
    def question(self, db):
        return make_question(
            db,
            make_subject(db),
            qtype=QuestionType.FILL_BLANK,
            marks=1.0,
            negative=0.25,
            spec={"kind": "fill_blank", "accepted_answers": ["water", "H2O"]},
        )

    def test_any_accepted_answer_earns_full_marks(self, question):
        for given in ("water", "H2O"):
            outcome = score_response(
                question=question, text_answer=given, max_marks=1.0, negative_marking=True
            )
            assert outcome.is_correct, given

    def test_matching_ignores_case_by_default(self, question):
        assert score_response(
            question=question, text_answer="WATER", max_marks=1.0, negative_marking=False
        ).is_correct

    def test_surrounding_whitespace_is_not_a_wrong_answer(self, question):
        assert score_response(
            question=question, text_answer="  water  ", max_marks=1.0, negative_marking=False
        ).is_correct

    def test_a_wrong_answer_costs_the_penalty(self, question):
        outcome = score_response(
            question=question, text_answer="hydrogen", max_marks=1.0, negative_marking=True
        )
        assert outcome.awarded == -0.25

    def test_case_sensitivity_can_be_demanded(self, db):
        question = make_question(
            db,
            make_subject(db),
            qtype=QuestionType.FILL_BLANK,
            marks=1.0,
            spec={"kind": "fill_blank", "accepted_answers": ["NaCl"], "case_sensitive": True},
        )
        assert score_response(
            question=question, text_answer="NaCl", max_marks=1.0, negative_marking=False
        ).is_correct
        assert not score_response(
            question=question, text_answer="nacl", max_marks=1.0, negative_marking=False
        ).is_correct

    def test_substring_matching_is_off_unless_asked_for(self, db):
        strict = make_question(
            db,
            make_subject(db),
            qtype=QuestionType.FILL_BLANK,
            marks=1.0,
            spec={"kind": "fill_blank", "accepted_answers": ["water"]},
        )
        # Without it, "not water" is wrong - which is the point.
        assert not score_response(
            question=strict, text_answer="not water", max_marks=1.0, negative_marking=False
        ).is_correct


class TestTrueFalseScoring:
    def test_it_scores_through_the_same_path_as_an_mcq(self, db):
        question = make_question(
            db, make_subject(db), qtype=QuestionType.TRUE_FALSE, marks=1.0, negative=0.25
        )
        right = [str(o.id) for o in question.options if o.is_correct]
        wrong = [str(o.id) for o in question.options if not o.is_correct]

        assert score_answer(
            question=question,
            selected_option_ids=right,
            text_answer=None,
            max_marks=1.0,
            negative_marking=True,
        ).awarded == 1.0
        assert score_answer(
            question=question,
            selected_option_ids=wrong,
            text_answer=None,
            max_marks=1.0,
            negative_marking=True,
        ).awarded == -0.25


class TestDispatch:
    def test_it_routes_option_types_and_response_types_correctly(self, db):
        subject = make_subject(db)
        numerical = make_question(
            db,
            subject,
            qtype=QuestionType.NUMERICAL,
            marks=2.0,
            spec={"kind": "numerical", "answer": 7.0},
        )
        mcq = make_question(db, subject, qtype=QuestionType.MCQ, marks=2.0)

        assert score_answer(
            question=numerical,
            selected_option_ids=None,
            text_answer="7",
            max_marks=2.0,
            negative_marking=False,
        ).is_correct

        correct = [str(o.id) for o in mcq.options if o.is_correct]
        assert score_answer(
            question=mcq,
            selected_option_ids=correct,
            text_answer=None,
            max_marks=2.0,
            negative_marking=False,
        ).is_correct

    @pytest.mark.parametrize(
        "qtype", [QuestionType.CODING, QuestionType.LONG_ANSWER, QuestionType.IMAGE_UPLOAD]
    )
    def test_types_that_need_a_human_are_refused(self, db, qtype):
        question = make_question(db, make_subject(db), qtype=qtype, marks=5.0)
        with pytest.raises(ValueError, match="not auto-scorable"):
            score_answer(
                question=question,
                selected_option_ids=None,
                text_answer="something",
                max_marks=5.0,
                negative_marking=False,
            )
