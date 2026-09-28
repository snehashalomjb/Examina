"""Populate and verify realistic question-bank fixtures for every supported subject.

This focused, idempotent companion to the full demo seed writes two unique
questions for every combination of ``mcq`` / ``multi_select`` / ``short_answer``
and ``easy`` / ``medium`` / ``hard``. Every row is bound to the UUID of the
subject with the matching stable ``Subject.code``.

Run from ``backend`` with::

    uv run python -m app.seed_questions

Existing examiner-authored questions are never changed or deleted. An unknown
subject code stops the seed before any write, preventing a misleading partial run.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging_config import get_logger, setup_logging
from app.db.models import (
    Difficulty,
    Question,
    QuestionOption,
    QuestionSource,
    QuestionStatus,
    QuestionType,
    Subject,
)
from app.db.session import SessionLocal
from app.seed_question_catalog import SUBJECT_FIXTURES, FixtureQuestion
from app.services.question_import import fingerprint
from app.services.validators import OptionDraft, validate_question
from app.subject_translation_catalog import seed_subject_translations

logger = get_logger("seed_questions")

SEED_TAG = "question-bank-fixture-v1"
KEY_PREFIX = "fixture"
REQUIRED_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.SHORT_ANSWER}
REQUIRED_DIFFICULTIES = {Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD}
REQUIRED_PER_BUCKET = 2
FIXTURE_KEY_RE = re.compile(r"^fixture:(?P<code>[a-z0-9-]+):(?P<number>\d{2,})$")


class SeedConfigurationError(RuntimeError):
    """The database or fixture catalogue cannot safely be seeded."""


@dataclass
class SeedReport:
    inserted: int = 0
    existing: int = 0
    subjects: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.existing


def fixture_key(code: str, index: int) -> str:
    return f"{KEY_PREFIX}:{code.lower()}:{index:02d}"


def _validate_catalogue() -> None:
    """Fail before opening a write transaction if fixtures are incomplete."""
    if not SUBJECT_FIXTURES:
        raise SeedConfigurationError("The fixture catalogue is empty")

    seen_bodies: dict[str, str] = {}
    seen_keys: set[str] = set()
    problems: list[str] = []

    for code, definition in SUBJECT_FIXTURES.items():
        if definition.code != code:
            problems.append(f"catalogue key {code!r} declares {definition.code!r}")
        if not definition.name.strip() or not definition.description.strip():
            problems.append(f"{code}: name and description are required")
        if not definition.questions:
            problems.append(f"{code}: no questions")
            continue

        counts = Counter((q.question_type, q.difficulty) for q in definition.questions)
        for question_type in sorted(REQUIRED_TYPES, key=lambda item: item.value):
            for difficulty in sorted(REQUIRED_DIFFICULTIES, key=lambda item: item.value):
                count = counts[(question_type, difficulty)]
                if count < REQUIRED_PER_BUCKET:
                    problems.append(
                        f"{code}: {question_type.value}/{difficulty.value} has {count}; "
                        f"need at least {REQUIRED_PER_BUCKET}"
                    )

        for index, fixture in enumerate(definition.questions, start=1):
            key = fixture_key(code, index)
            if key in seen_keys:
                problems.append(f"duplicate fixture key {key}")
            seen_keys.add(key)
            body_key = fingerprint(fixture.body)
            owner = seen_bodies.get(body_key)
            if owner:
                problems.append(f"{code}: duplicate body also used by {owner}")
            else:
                seen_bodies[body_key] = code
            if (
                not fixture.body.strip()
                or len(fixture.body) > 20_000
                or not fixture.topic.strip()
                or len(fixture.topic) > 120
                or not fixture.explanation.strip()
            ):
                problems.append(f"{key}: body, topic, and explanation have invalid lengths")
            option_texts = [option.text.strip().casefold() for option in fixture.options]
            if len(option_texts) != len(set(option_texts)):
                problems.append(f"{key}: options must be unique")
            try:
                question_type = QuestionType(fixture.question_type)
                validate_question(
                    question_type=question_type,
                    body=fixture.body,
                    marks=fixture.marks,
                    negative_marks=fixture.negative_marks,
                    options=[
                        OptionDraft(option.text, option.is_correct, index)
                        for index, option in enumerate(fixture.options)
                    ],
                    model_answer=fixture.model_answer,
                    min_words=fixture.min_words,
                    max_words=fixture.max_words,
                )
            except (ValueError, TypeError) as exc:
                problems.append(f"{key}: {exc}")

    if problems:
        raise SeedConfigurationError(
            "Invalid fixture catalogue:\n- " + "\n- ".join(problems)
        )


def _resolve_subjects(db: Session) -> dict[str, Subject]:
    """Create missing canonical subjects and return them keyed by stable code."""
    existing = {row.code: row for row in db.scalars(select(Subject))}
    unknown = sorted(set(existing) - set(SUBJECT_FIXTURES))
    if unknown:
        raise SeedConfigurationError(
            "Refusing to skip database subjects without a vetted fixture catalogue: "
            + ", ".join(unknown)
            + ". Add each code to app.seed_question_catalog before running this seed."
        )

    for code, definition in SUBJECT_FIXTURES.items():
        if code not in existing and definition.create_if_missing:
            row = Subject(code=code, name=definition.name, description=definition.description)
            db.add(row)
            existing[code] = row
            logger.info("Created canonical subject %s (%s)", code, definition.name)
    db.flush()
    seed_subject_translations(db, existing.values())
    return existing


def _fixture_key_from_tags(tags: list[str] | None) -> str | None:
    for tag in tags or []:
        if tag.startswith(f"{KEY_PREFIX}:"):
            return tag
    return None


def _load_existing_fixtures(db: Session) -> tuple[dict[str, Question], set[tuple[object, str]]]:
    rows = db.scalars(
        select(Question)
        .where(Question.tags.contains([SEED_TAG]))
        .options(selectinload(Question.options))
    ).all()
    by_key: dict[str, Question] = {}
    bodies = {
        (subject_id, fingerprint(body))
        for subject_id, body in db.execute(
            select(Question.subject_id, Question.body).where(
                Question.is_active,
                Question.origin_exam_id.is_(None),
            )
        ).all()
    }
    for row in rows:
        key = _fixture_key_from_tags(row.tags)
        if key is None or not FIXTURE_KEY_RE.fullmatch(key):
            raise SeedConfigurationError(f"Question {row.id} has an invalid fixture key")
        if key in by_key:
            raise SeedConfigurationError(f"Duplicate fixture key in database: {key}")
        by_key[key] = row
        bodies.add((row.subject_id, fingerprint(row.body)))
    return by_key, bodies


def _make_question(
    *, subject: Subject, code: str, index: int, fixture: FixtureQuestion
) -> Question:
    question = Question(
        subject_id=subject.id,
        question_type=QuestionType(fixture.question_type),
        category=SUBJECT_FIXTURES[code].category,
        topic=fixture.topic,
        difficulty=fixture.difficulty,
        body=fixture.body,
        model_answer=fixture.model_answer,
        explanation=fixture.explanation,
        marks=fixture.marks,
        negative_marks=fixture.negative_marks,
        min_words=fixture.min_words,
        max_words=fixture.max_words,
        tags=[SEED_TAG, fixture_key(code, index), code.lower(), fixture.topic.lower()],
        status=QuestionStatus.PUBLISHED,
        is_active=True,
        source=QuestionSource.IMPORTED,
    )
    for order, option in enumerate(fixture.options):
        question.options.append(
            QuestionOption(
                text=option.text,
                is_correct=option.is_correct,
                order_index=order,
            )
        )
    return question


def _assert_fixture_matches(
    row: Question,
    *,
    code: str,
    subject: Subject,
    fixture: FixtureQuestion,
) -> None:
    if row.subject_id != subject.id:
        raise SeedConfigurationError(
            f"Fixture {row.id} is linked to the wrong subject: "
            f"{row.subject_id} != {subject.id}"
        )
    expected = (
        row.question_type.value,
        row.category.value,
        row.difficulty.value,
        row.topic,
        row.body,
        row.model_answer,
        row.explanation,
        row.marks,
        row.negative_marks,
        row.min_words,
        row.max_words,
    )
    actual = (
        fixture.question_type,
        SUBJECT_FIXTURES[code].category.value,
        fixture.difficulty.value,
        fixture.topic,
        fixture.body,
        fixture.model_answer,
        fixture.explanation,
        fixture.marks,
        fixture.negative_marks,
        fixture.min_words,
        fixture.max_words,
    )
    if expected != actual:
        raise SeedConfigurationError(f"Fixture {row.id} no longer matches the catalogue")
    expected_options = tuple((o.text, o.is_correct) for o in fixture.options)
    actual_options = tuple((o.text, o.is_correct) for o in row.options)
    if expected_options != actual_options:
        raise SeedConfigurationError(f"Fixture {row.id} options no longer match the catalogue")


def seed_questions(db: Session) -> SeedReport:
    """Insert missing fixtures and return a report; caller owns commit/rollback."""
    _validate_catalogue()
    subjects = _resolve_subjects(db)
    by_key, existing_bodies = _load_existing_fixtures(db)
    report = SeedReport(subjects=sum(code in subjects for code in SUBJECT_FIXTURES))

    new_questions: list[Question] = []
    for code, definition in SUBJECT_FIXTURES.items():
        subject = subjects.get(code)
        if subject is None:
            continue
        for index, fixture in enumerate(definition.questions, start=1):
            key = fixture_key(code, index)
            existing = by_key.get(key)
            if existing is not None:
                _assert_fixture_matches(existing, code=code, subject=subject, fixture=fixture)
                report.existing += 1
                continue
            body_key = (subject.id, fingerprint(fixture.body))
            if body_key in existing_bodies:
                raise SeedConfigurationError(
                    f"{code} fixture {key} duplicates an existing question body"
                )
            new_questions.append(
                _make_question(subject=subject, code=code, index=index, fixture=fixture)
            )
            existing_bodies.add(body_key)

    db.add_all(new_questions)
    db.flush()
    report.inserted = len(new_questions)
    return report


def verify_questions(db: Session) -> dict[str, int]:
    """Verify subject mapping, required coverage, options, and fixture completeness."""
    _validate_catalogue()
    subjects = {row.code: row for row in db.scalars(select(Subject))}
    rows = db.scalars(
        select(Question)
        .where(Question.tags.contains([SEED_TAG]))
        .options(selectinload(Question.options))
    ).all()
    by_key: dict[str, Question] = {}
    for row in rows:
        key = _fixture_key_from_tags(row.tags)
        if key is None or key in by_key:
            raise SeedConfigurationError(f"Invalid or duplicate fixture key in database: {key}")
        by_key[key] = row

    coverage: Counter[tuple[str, str, str]] = Counter()
    for code, definition in SUBJECT_FIXTURES.items():
        subject = subjects.get(code)
        if subject is None:
            continue
        for index, fixture in enumerate(definition.questions, start=1):
            key = fixture_key(code, index)
            row = by_key.get(key)
            if row is None:
                raise SeedConfigurationError(f"Missing fixture {key}")
            _assert_fixture_matches(row, code=code, subject=subject, fixture=fixture)
            if not row.is_active or row.status is not QuestionStatus.PUBLISHED:
                raise SeedConfigurationError(f"Fixture {key} is not active and published")
            if row.source is not QuestionSource.IMPORTED:
                raise SeedConfigurationError(f"Fixture {key} has the wrong source")
            coverage[(code, fixture.question_type, fixture.difficulty.value)] += 1

    for code in SUBJECT_FIXTURES:
        if code not in subjects:
            continue
        for qtype in REQUIRED_TYPES:
            for difficulty in REQUIRED_DIFFICULTIES:
                count = coverage[(code, qtype.value, difficulty.value)]
                if count < REQUIRED_PER_BUCKET:
                    raise SeedConfigurationError(
                        f"{code}: persisted {qtype.value}/{difficulty.value} count is {count}"
                    )

    return {
        "subjects": len(subjects),
        "fixtures": len(rows),
        "subjects_with_fixtures": len({row.subject_id for row in rows}),
    }


def main() -> None:
    setup_logging()
    db = SessionLocal()
    try:
        report = seed_questions(db)
        summary = verify_questions(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Question fixture seed complete:")
    print(f"  - subjects checked: {summary['subjects']}")
    print(f"  - fixture rows: {summary['fixtures']}")
    print(f"  - newly inserted: {report.inserted}")
    print(f"  - already present: {report.existing}")
    print("  - coverage: 2+ each of mcq, multi_select, short_answer x easy, medium, hard")


if __name__ == "__main__":
    main()