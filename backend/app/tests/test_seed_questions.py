"""Regression tests for the focused question-bank fixture seed."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Question, QuestionType, Subject
from app.seed_question_catalog import SUBJECT_FIXTURES
from app.seed_questions import (
    REQUIRED_DIFFICULTIES,
    REQUIRED_PER_BUCKET,
    REQUIRED_TYPES,
    SEED_TAG,
    _validate_catalogue,
    seed_questions,
    verify_questions,
)


def test_catalogue_covers_every_subject_and_bucket() -> None:
    _validate_catalogue()
    assert len(SUBJECT_FIXTURES) == 21
    for definition in SUBJECT_FIXTURES.values():
        assert len(definition.questions) == 18
        counts = Counter((q.question_type, q.difficulty) for q in definition.questions)
        for question_type in REQUIRED_TYPES:
            for difficulty in REQUIRED_DIFFICULTIES:
                assert counts[(question_type.value, difficulty)] == REQUIRED_PER_BUCKET


def test_subject_translation_catalogue_covers_every_canonical_subject() -> None:
    from app.seed_question_catalog import SUBJECT_FIXTURES
    from app.subject_translation_catalog import SUBJECT_NAME_TRANSLATIONS

    expected_locales = {"ml", "ta", "hi", "kn", "te"}
    assert set(SUBJECT_NAME_TRANSLATIONS) == set(SUBJECT_FIXTURES)
    for code, translations in SUBJECT_NAME_TRANSLATIONS.items():
        assert set(translations) == expected_locales, code
        assert all(translations[locale].strip() for locale in expected_locales), code


def test_seed_is_idempotent_and_keeps_subject_mapping(db: Session) -> None:
    for definition in SUBJECT_FIXTURES.values():
        db.add(
            Subject(
                code=definition.code,
                name=definition.name,
                description=definition.description,
            )
        )
    db.flush()

    first = seed_questions(db)
    assert first.inserted == 18 * len(SUBJECT_FIXTURES)
    assert first.existing == 0
    assert verify_questions(db) == {
        "subjects": len(SUBJECT_FIXTURES),
        "fixtures": 18 * len(SUBJECT_FIXTURES),
        "subjects_with_fixtures": len(SUBJECT_FIXTURES),
    }

    second = seed_questions(db)
    assert second.inserted == 0
    assert second.existing == 18 * len(SUBJECT_FIXTURES)

    rows = db.scalars(select(Question).where(Question.tags.contains([SEED_TAG]))).all()
    assert len(rows) == 18 * len(SUBJECT_FIXTURES)
    subjects = {subject.code: subject for subject in db.scalars(select(Subject)).all()}
    for row in rows:
        code = next(
            tag.split(":", 2)[1].upper()
            for tag in row.tags
            if tag.startswith("fixture:")
        )
        assert subjects[code].id == row.subject_id
        assert row.question_type in REQUIRED_TYPES
        assert row.difficulty in REQUIRED_DIFFICULTIES
        assert row.body and row.topic and row.explanation and row.model_answer
        if row.question_type is QuestionType.MCQ:
            assert len(row.options) == 4
            assert sum(option.is_correct for option in row.options) == 1
        elif row.question_type is QuestionType.MULTI_SELECT:
            assert len(row.options) == 4
            assert sum(option.is_correct for option in row.options) == 2
        else:
            assert row.options == []