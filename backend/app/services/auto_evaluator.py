"""Automatic scoring for every question type the platform can mark without a human.

Two families, both pure functions over (question, response) so they are trivially
testable and carry no database or request state:

- **option-bearing** - mcq, multi_select, true_false. Scored by comparing selected
  option ids against the key. ``score_objective``.
- **typed response** - numerical, fill_blank. Scored by comparing what the candidate
  typed against the question's ``spec``. ``score_response``.

``score_answer`` dispatches to whichever applies, and is what the exam engine calls.
Everything else - short/long answer, image upload, coding - needs a grader and is routed
to the review queue instead.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.db.models import Question, QuestionType
from app.db.models.enums import AUTO_SCORED_TYPES, OPTION_BEARING_TYPES, RESPONSE_TYPES
from app.services.question_spec import FillBlankSpec, NumericalSpec, load_spec


@dataclass(frozen=True)
class ScoreOutcome:
    awarded: float
    max_marks: float
    is_correct: bool
    is_answered: bool


def _correct_option_ids(question: Question) -> set[str]:
    return {str(o.id) for o in question.options if o.is_correct}


def score_objective(
    *,
    question: Question,
    selected_option_ids: list[str] | None,
    max_marks: float,
    negative_marking: bool,
    partial_credit: bool = False,
) -> ScoreOutcome:
    """Score an MCQ or multi-select answer.

    MCQ: exact match earns full marks; a wrong pick costs ``negative_marks`` when negative
    marking is on; a blank earns 0 and never attracts a penalty.

    Multi-select: all-or-nothing by default. With ``partial_credit`` on, marks scale with
    the fraction of correct options selected, but any incorrect selection zeroes the
    answer - partial credit rewards incomplete knowledge, not guessing everything.
    """
    if question.question_type not in OPTION_BEARING_TYPES:
        raise ValueError(f"{question.question_type.value} is not scored from options")

    selected = {str(o) for o in (selected_option_ids or [])}
    correct = _correct_option_ids(question)
    penalty = question.negative_marks if negative_marking else 0.0

    if not selected:
        return ScoreOutcome(0.0, max_marks, is_correct=False, is_answered=False)

    if question.question_type is not QuestionType.MULTI_SELECT:
        # mcq and true_false are single-answer and score identically.
        # Defensive: a client that sends several ids for either is treated as wrong.
        is_correct = len(selected) == 1 and selected == correct
        awarded = max_marks if is_correct else -penalty
        return ScoreOutcome(awarded, max_marks, is_correct, is_answered=True)

    # multi_select
    if selected == correct:
        return ScoreOutcome(max_marks, max_marks, True, True)

    wrong_picks = selected - correct
    if partial_credit and not wrong_picks and correct:
        fraction = len(selected & correct) / len(correct)
        return ScoreOutcome(round(max_marks * fraction, 4), max_marks, False, True)

    return ScoreOutcome(-penalty, max_marks, False, True)


# --------------------------------------------------------------- typed responses
_WHITESPACE = re.compile(r"\s+")
#: Accepts "3", "-2.5", "1e-3", "1,234.5" and unicode minus. Anything else is not a
#: number the candidate meant to type.
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def parse_number(raw: str | None) -> float | None:
    """Read a candidate's numeric answer, or None when it is not a number.

    Deliberately forgiving about how people type numbers and deliberately strict about
    what counts as one: thousands separators and a unicode minus are accepted, but
    "about 5" is not silently read as 5.
    """
    if raw is None:
        return None
    text = unicodedata.normalize("NFKC", raw).strip()
    if not text:
        return None
    # A unicode minus or en-dash pasted from a document is still a minus sign.
    text = text.replace("−", "-").replace("–", "-")
    text = text.replace(",", "").replace(" ", "")
    if not _NUMBER.match(text):
        return None
    try:
        return float(text)
    except ValueError:  # pragma: no cover - the regex already guarantees this parses
        return None


def _normalise_text(value: str, *, case_sensitive: bool, collapse_whitespace: bool) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    if collapse_whitespace:
        text = _WHITESPACE.sub(" ", text)
    return text if case_sensitive else text.casefold()


def _score_numerical(
    *, spec: NumericalSpec, given: str | None, max_marks: float, penalty: float
) -> ScoreOutcome:
    value = parse_number(given)
    if value is None:
        # Nothing usable typed. Unparseable text is *answered but wrong* rather than
        # blank - the candidate did attempt it - but a truly empty box is unanswered.
        if given is None or not given.strip():
            return ScoreOutcome(0.0, max_marks, is_correct=False, is_answered=False)
        return ScoreOutcome(-penalty, max_marks, is_correct=False, is_answered=True)

    target = spec.answer
    absolute_ok = abs(value - target) <= spec.tolerance
    relative_ok = False
    if spec.relative_tolerance:
        # Relative to the expected value, not the given one, so a wild answer cannot
        # widen its own acceptance band.
        relative_ok = abs(value - target) <= abs(target) * spec.relative_tolerance

    is_correct = absolute_ok or relative_ok
    return ScoreOutcome(
        max_marks if is_correct else -penalty, max_marks, is_correct, is_answered=True
    )


def _score_fill_blank(
    *, spec: FillBlankSpec, given: str | None, max_marks: float, penalty: float
) -> ScoreOutcome:
    if given is None or not given.strip():
        return ScoreOutcome(0.0, max_marks, is_correct=False, is_answered=False)

    candidate = _normalise_text(
        given,
        case_sensitive=spec.case_sensitive,
        collapse_whitespace=spec.normalise_whitespace,
    )
    accepted = [
        _normalise_text(
            answer,
            case_sensitive=spec.case_sensitive,
            collapse_whitespace=spec.normalise_whitespace,
        )
        for answer in spec.accepted_answers
        if answer.strip()
    ]

    if spec.allow_substring:
        is_correct = any(answer and answer in candidate for answer in accepted)
    else:
        is_correct = candidate in accepted

    return ScoreOutcome(
        max_marks if is_correct else -penalty, max_marks, is_correct, is_answered=True
    )


def score_response(
    *,
    question: Question,
    text_answer: str | None,
    max_marks: float,
    negative_marking: bool,
) -> ScoreOutcome:
    """Score a numerical or fill-in-the-blank answer against the question's spec."""
    if question.question_type not in RESPONSE_TYPES:
        raise ValueError(f"{question.question_type.value} is not scored from a typed response")

    spec = load_spec(question.question_type, question.spec)
    if spec is None:
        # The spec is the answer key. Without a readable one there is nothing to mark
        # against, so the answer goes to a human rather than being guessed at.
        raise ValueError(
            f"Question {question.id} is {question.question_type.value} but has no usable spec"
        )

    penalty = question.negative_marks if negative_marking else 0.0

    if isinstance(spec, NumericalSpec):
        return _score_numerical(
            spec=spec, given=text_answer, max_marks=max_marks, penalty=penalty
        )
    return _score_fill_blank(
        spec=spec, given=text_answer, max_marks=max_marks, penalty=penalty
    )


def score_answer(
    *,
    question: Question,
    selected_option_ids: list[str] | None,
    text_answer: str | None,
    max_marks: float,
    negative_marking: bool,
    partial_credit: bool = False,
) -> ScoreOutcome:
    """Score any auto-scorable question, dispatching on its type.

    The single entry point the exam engine uses, so adding an auto-scorable type means
    teaching this one function rather than hunting for every ``question_type ==`` check.
    """
    if question.question_type not in AUTO_SCORED_TYPES:
        raise ValueError(f"{question.question_type.value} is not auto-scorable")

    if question.question_type in OPTION_BEARING_TYPES:
        return score_objective(
            question=question,
            selected_option_ids=selected_option_ids,
            max_marks=max_marks,
            negative_marking=negative_marking,
            partial_credit=partial_credit,
        )

    return score_response(
        question=question,
        text_answer=text_answer,
        max_marks=max_marks,
        negative_marking=negative_marking,
    )
