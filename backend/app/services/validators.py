"""Domain validation that must hold regardless of which endpoint is writing.

Kept out of the Pydantic schemas so the same rules apply to seeding, bulk import and the
API alike. Every rule here has a matching test in app/tests/test_validators.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.db.models.enums import (
    CONTAINER_TYPES,
    OPTION_BEARING_TYPES,
    Difficulty,
    QuestionType,
)
from app.services.question_spec import SpecError, validate_spec
from app.services.text_metrics import validate_word_bounds


class ValidationError(ValueError):
    """Raised for a domain rule breach; the API turns this into a 422."""


@dataclass
class OptionDraft:
    text: str
    is_correct: bool = False
    order_index: int = 0


def validate_question(
    *,
    question_type: QuestionType,
    body: str,
    marks: float,
    negative_marks: float,
    options: Sequence[OptionDraft] | None,
    model_answer: str | None,
    min_words: int | None = None,
    max_words: int | None = None,
    spec: dict | None = None,
    image_key: str | None = None,
) -> dict | None:
    """Enforce the per-type rules from the project spec.

    Returns the normalised ``spec`` to store - parsing it is part of validating it, so
    the caller saves what this function hands back rather than the raw payload.
    """
    if not body or not body.strip():
        # A diagram question can *be* its figure - "Which architecture is this?" with the
        # picture carrying the content. An empty body is only an error with no image to
        # carry it.
        if not image_key:
            raise ValidationError("Question body cannot be empty")

    if question_type in CONTAINER_TYPES:
        # A passage is the text its children are asked about. It is never answered and
        # never scored, so it is the one type that must carry no marks - see below.
        if marks:
            raise ValidationError(
                "A passage carries no marks of its own - the marks belong to its questions"
            )
    elif marks is None or marks <= 0:
        raise ValidationError("marks must be greater than 0")

    if negative_marks < 0:
        raise ValidationError("negative_marks cannot be negative")

    if negative_marks > marks:
        raise ValidationError("negative_marks cannot exceed the question's marks")

    options = list(options or [])
    correct = [o for o in options if o.is_correct]

    if question_type in OPTION_BEARING_TYPES:
        if question_type is QuestionType.TRUE_FALSE:
            # Exactly two options, exactly one right. Anything else is not true/false.
            if len(options) != 2:
                raise ValidationError(
                    f"A true/false question needs exactly 2 options, got {len(options)}"
                )
            if len(correct) != 1:
                raise ValidationError(
                    f"A true/false question must have exactly one correct option, "
                    f"got {len(correct)}"
                )
        elif len(options) < 2:
            raise ValidationError(
                f"{question_type.value} questions need at least 2 options, got {len(options)}"
            )

        if any(not o.text or not o.text.strip() for o in options):
            raise ValidationError("Option text cannot be empty")

        if question_type is QuestionType.MCQ and len(correct) != 1:
            raise ValidationError(
                f"An MCQ must have exactly one correct option, got {len(correct)}"
            )
        if question_type is QuestionType.MULTI_SELECT and len(correct) < 1:
            raise ValidationError("A multi-select question needs at least one correct option")
        if question_type is QuestionType.MULTI_SELECT and len(correct) == len(options):
            raise ValidationError("A multi-select question cannot have every option marked correct")
    else:
        if options:
            raise ValidationError(f"{question_type.value} questions must not define options")

    if question_type in {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}:
        if not model_answer or not model_answer.strip():
            raise ValidationError(
                f"{question_type.value} questions require a model answer for grading"
            )

    try:
        validate_word_bounds(
            min_words=min_words, max_words=max_words, question_type=question_type
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if question_type is QuestionType.IMAGE_UPLOAD and marks <= 0:
        # Explicit per the spec, even though the general marks rule already covers it.
        raise ValidationError("image_upload questions must define max marks")

    # Parsing the spec *is* validating it, so hand back what should be stored rather than
    # letting the caller save the unparsed payload.
    try:
        return validate_spec(question_type, spec)
    except SpecError as exc:
        raise ValidationError(str(exc)) from exc


def validate_exam_window(*, starts_at: datetime, ends_at: datetime, duration_minutes: int) -> None:
    if ends_at <= starts_at:
        raise ValidationError("The exam window must end after it starts")
    if duration_minutes <= 0:
        raise ValidationError("duration_minutes must be greater than 0")

    window_minutes = (ends_at - starts_at).total_seconds() / 60
    if duration_minutes > window_minutes:
        raise ValidationError(
            f"Duration ({duration_minutes} min) exceeds the exam window ({int(window_minutes)} min)"
        )


def normalise_selection_rules(raw: dict | None) -> list[dict]:
    """Validate and normalise the ``selection_rules`` JSON blob.

    Shape: {"rules": [{"question_type": "mcq", "difficulty": "easy"|null, "count": 10}]}
    ``difficulty: null`` means "any difficulty".
    """
    rules = (raw or {}).get("rules") or []
    if not isinstance(rules, list) or not rules:
        raise ValidationError("selection_rules must contain at least one rule")

    normalised: list[dict] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValidationError(f"Rule #{index + 1} is not an object")
        try:
            qtype = QuestionType(rule["question_type"])
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"Rule #{index + 1} has an unknown question_type") from exc

        difficulty_raw = rule.get("difficulty")
        difficulty = None
        if difficulty_raw:
            try:
                difficulty = Difficulty(difficulty_raw)
            except ValueError as exc:
                raise ValidationError(
                    f"Rule #{index + 1} has an unknown difficulty '{difficulty_raw}'"
                ) from exc

        count = rule.get("count")
        if not isinstance(count, int) or count <= 0:
            raise ValidationError(f"Rule #{index + 1} needs a positive integer count")

        normalised.append(
            {
                "question_type": qtype.value,
                "difficulty": difficulty.value if difficulty else None,
                "count": count,
            }
        )
    return normalised
