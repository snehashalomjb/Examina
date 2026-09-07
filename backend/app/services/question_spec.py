"""Typed configuration for the question types that need more than options and a body.

``questions.spec`` is one JSONB column rather than a dozen sparse ones, because the shape
genuinely differs per type and only the validator and scorer for that type ever read it.
This module is what stops that column becoming a bag of untyped dicts: every write goes
through ``validate_spec``, which parses into a real model and raises on anything the type
does not define. What comes back out of ``load_spec`` is the same model, so scorers work
against attributes rather than ``spec.get("tolerance") or 0``.

One rule runs through all of it: nothing here ever holds the answer to a question the
candidate is currently sitting. Specs are examiner-side configuration and are stripped
from the paper the browser receives - see ``PaperQuestion`` in the exam-session schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import QuestionType


class SpecError(ValueError):
    """A ``spec`` payload does not match what its question type requires."""


class _StrictModel(BaseModel):
    """Reject unknown keys.

    A typo in an examiner's payload - ``case_sensitve`` - would otherwise be accepted,
    stored, and silently ignored at scoring time, which reads as "the platform got the
    marking wrong". Better to refuse the write.
    """

    model_config = ConfigDict(extra="forbid")


class NumericalSpec(_StrictModel):
    """A numeric response, marked correct within a tolerance.

    Tolerance is what makes this type worth having: ``9.81`` and ``9.8`` are the same
    answer in physics, and asking an examiner to enumerate acceptable strings is how
    numerical questions get marked wrong.
    """

    kind: Literal["numerical"] = "numerical"

    answer: float = Field(..., description="The exact expected value")
    #: Absolute tolerance: |given - answer| <= tolerance. Zero demands an exact match.
    tolerance: float = Field(default=0.0, ge=0)
    #: Relative tolerance as a fraction, e.g. 0.01 for +/-1%. Applied alongside the
    #: absolute one; an answer inside *either* band is accepted, which is what a
    #: candidate expects when a question says "to within 1%".
    relative_tolerance: float | None = Field(default=None, ge=0, le=1)
    unit: str | None = Field(default=None, max_length=40)


class FillBlankSpec(_StrictModel):
    """One or more accepted strings for a fill-in-the-blank.

    Multiple accepted answers are the norm, not the exception - "H2O" and "water" are
    both right, and a single expected string turns a correct answer into a wrong one.
    """

    kind: Literal["fill_blank"] = "fill_blank"

    accepted_answers: list[str] = Field(..., min_length=1, max_length=50)
    case_sensitive: bool = False
    #: Collapse runs of whitespace and trim before comparing. On by default: a trailing
    #: space is not a wrong answer.
    normalise_whitespace: bool = True
    #: Accept an answer that merely contains an accepted string. Off by default, because
    #: it turns "not water" into a correct answer for "water".
    allow_substring: bool = False

    @model_validator(mode="after")
    def _non_empty(self) -> FillBlankSpec:
        if not [a for a in self.accepted_answers if a.strip()]:
            raise ValueError("accepted_answers cannot be all blank")
        return self


class CodingSampleCase(_StrictModel):
    input: str = ""
    output: str = ""
    explanation: str | None = None


class CodingSpec(_StrictModel):
    """A programming question.

    No execution yet: the candidate writes code, the platform stores it, and an examiner
    (with the grader's suggestion beside them) marks it. ``sample_cases`` are shown to the
    candidate as part of the problem statement; they are not a test harness.
    """

    kind: Literal["coding"] = "coding"

    languages: list[Literal["python", "java", "cpp", "javascript"]] = Field(
        ..., min_length=1, description="Languages the candidate may answer in"
    )
    default_language: Literal["python", "java", "cpp", "javascript"] | None = None

    input_format: str = Field(..., min_length=1)
    output_format: str = Field(..., min_length=1)
    constraints: str = Field(..., min_length=1)
    sample_cases: list[CodingSampleCase] = Field(..., min_length=1, max_length=10)

    #: Pre-filled editor contents per language, e.g. a function signature to complete.
    starter_code: dict[str, str] = Field(default_factory=dict)
    time_limit_seconds: float | None = Field(default=None, gt=0, le=60)

    @model_validator(mode="after")
    def _language_consistency(self) -> CodingSpec:
        if self.default_language and self.default_language not in self.languages:
            raise ValueError("default_language must be one of the offered languages")
        unknown = set(self.starter_code) - set(self.languages)
        if unknown:
            raise ValueError(
                f"starter_code has entries for languages not offered: {sorted(unknown)}"
            )
        return self


class PassageSpec(_StrictModel):
    """A passage or case study that child questions are asked about.

    The passage itself is never scored - it carries no marks and no answer. It exists so
    the runner can render one body above a group of questions instead of repeating it.
    """

    kind: Literal["passage"] = "passage"

    #: Shown above the child questions. Falls back to the question body when unset.
    passage_text: str | None = None
    source: str | None = Field(default=None, max_length=200)
    #: Keep the passage on screen while answering its children. Almost always wanted;
    #: switchable for a short case study that fits above the question anyway.
    sticky: bool = True


class TrueFalseSpec(_StrictModel):
    """Optional extras for a true/false question.

    The answer itself lives in ``question_options`` like any other option-bearing type,
    so a true/false question scores through exactly the same path as an MCQ. This spec
    only carries display preferences.
    """

    kind: Literal["true_false"] = "true_false"

    true_label: str = Field(default="True", max_length=40)
    false_label: str = Field(default="False", max_length=40)


#: Which model governs which type. A type absent from this map takes no spec at all.
SPEC_MODELS: dict[QuestionType, type[BaseModel]] = {
    QuestionType.NUMERICAL: NumericalSpec,
    QuestionType.FILL_BLANK: FillBlankSpec,
    QuestionType.CODING: CodingSpec,
    QuestionType.PASSAGE: PassageSpec,
    QuestionType.TRUE_FALSE: TrueFalseSpec,
}

#: Types that cannot be saved without a spec - their spec *is* the answer key or the
#: problem statement, so a question without one is unanswerable rather than merely bare.
SPEC_REQUIRED = {QuestionType.NUMERICAL, QuestionType.FILL_BLANK, QuestionType.CODING}


def validate_spec(question_type: QuestionType, raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Parse and normalise a spec payload. Returns the JSON to store, or None.

    Raises ``SpecError`` when the payload is wrong for the type, missing where required,
    or supplied for a type that does not take one.
    """
    model = SPEC_MODELS.get(question_type)

    if model is None:
        if raw:
            raise SpecError(
                f"{question_type.value} questions do not take a spec; "
                f"remove it or change the question type"
            )
        return None

    if not raw:
        if question_type in SPEC_REQUIRED:
            raise SpecError(
                f"{question_type.value} questions need a spec - "
                f"it holds the answer key and the problem statement"
            )
        # Optional spec (true_false, passage): store the defaults so the runner always
        # has something concrete to read rather than branching on null.
        return model().model_dump(mode="json")

    try:
        parsed = model.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - pydantic's message is the useful one
        raise SpecError(_readable(exc)) from exc

    return parsed.model_dump(mode="json")


def load_spec(question_type: QuestionType, raw: dict[str, Any] | None) -> BaseModel | None:
    """Rehydrate a stored spec into its model. Returns None when the type takes none.

    Tolerant on the way out where ``validate_spec`` is strict on the way in: a row
    written before a field existed must still score rather than raise mid-exam.
    """
    model = SPEC_MODELS.get(question_type)
    if model is None or not raw:
        return None
    try:
        return model.model_validate(raw)
    except Exception:  # noqa: BLE001 - a malformed stored spec must not break scoring
        return None


def _readable(exc: Exception) -> str:
    """Flatten a pydantic ValidationError into one line an examiner can act on."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return str(exc)
    parts = []
    for error in errors()[:4]:
        location = ".".join(str(p) for p in error.get("loc", ())) or "spec"
        parts.append(f"{location}: {error.get('msg', 'invalid')}")
    return "; ".join(parts) or str(exc)


#: Fields that are safe to send to a candidate mid-exam, per type. Everything not listed
#: here stays server-side. The absent entries are the point: NumericalSpec.answer and
#: FillBlankSpec.accepted_answers are answer keys, so those types project to nothing.
CANDIDATE_SAFE_FIELDS: dict[QuestionType, frozenset[str]] = {
    QuestionType.CODING: frozenset(
        {
            "languages",
            "default_language",
            "input_format",
            "output_format",
            "constraints",
            "sample_cases",
            "starter_code",
            "time_limit_seconds",
        }
    ),
    QuestionType.PASSAGE: frozenset({"passage_text", "source", "sticky"}),
    QuestionType.TRUE_FALSE: frozenset({"true_label", "false_label"}),
}


def candidate_spec(
    question_type: QuestionType, raw: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Project a spec down to what the browser may see during the exam.

    An allowlist, not a denylist. A coding question genuinely needs its problem statement
    and sample cases on the paper; a numerical question's spec is nothing *but* the answer,
    so it projects to nothing. Adding a field to a spec model therefore cannot leak it by
    default - it has to be named here.
    """
    allowed = CANDIDATE_SAFE_FIELDS.get(question_type)
    if not allowed or not raw:
        return None

    projected = {key: value for key, value in raw.items() if key in allowed}
    return projected or None
