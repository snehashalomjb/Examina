"""The determinism guarantee: same candidate, same paper - always."""

from __future__ import annotations

import pytest

from app.db.models import Difficulty, QuestionType, UserRole
from app.services.paper_generator import (
    check_pool_satisfies_rules,
    compute_seed,
    generate_paper,
)
from app.services.validators import ValidationError
from app.tests.conftest import make_exam, make_question, make_subject, make_user


@pytest.fixture
def pool(db):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER)
    questions = []
    for difficulty in (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD):
        for _ in range(4):
            questions.append(
                make_question(db, subject, qtype=QuestionType.MCQ, difficulty=difficulty)
            )
    for _ in range(3):
        questions.append(
            make_question(
                db, subject, qtype=QuestionType.SHORT_ANSWER, difficulty=Difficulty.MEDIUM
            )
        )
    return subject, examiner, questions


def test_same_candidate_gets_an_identical_paper_twice(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[
            {"question_type": "mcq", "difficulty": "easy", "count": 3},
            {"question_type": "short_answer", "difficulty": None, "count": 2},
        ],
    )

    seed_a, entries_a = generate_paper(exam=exam, candidate_id=candidate.id)
    seed_b, entries_b = generate_paper(exam=exam, candidate_id=candidate.id)

    assert seed_a == seed_b
    assert [e.question_id for e in entries_a] == [e.question_id for e in entries_b]
    assert [e.option_order for e in entries_a] == [e.option_order for e in entries_b]


def test_different_candidates_get_different_papers(db, pool):
    subject, examiner, questions = pool
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "mcq", "difficulty": None, "count": 6}],
    )
    a = make_user(db, role=UserRole.CANDIDATE)
    b = make_user(db, role=UserRole.CANDIDATE)

    _, entries_a = generate_paper(exam=exam, candidate_id=a.id)
    _, entries_b = generate_paper(exam=exam, candidate_id=b.id)

    # With 12 MCQs choosing 6, identical ordering between two candidates would be a
    # 1-in-many-millions coincidence - treat equality as a determinism bug.
    assert [e.question_id for e in entries_a] != [e.question_id for e in entries_b]


def test_paper_honours_the_selection_rules(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[
            {"question_type": "mcq", "difficulty": "easy", "count": 2},
            {"question_type": "mcq", "difficulty": "hard", "count": 3},
            {"question_type": "short_answer", "difficulty": None, "count": 1},
        ],
    )
    _, entries = generate_paper(exam=exam, candidate_id=candidate.id)
    by_id = {q.id: q for q in questions}

    assert len(entries) == 6
    easy = [e for e in entries if by_id[e.question_id].difficulty is Difficulty.EASY]
    hard = [e for e in entries if by_id[e.question_id].difficulty is Difficulty.HARD]
    short = [e for e in entries if by_id[e.question_id].question_type is QuestionType.SHORT_ANSWER]
    assert len(easy) == 2
    assert len(hard) == 3
    assert len(short) == 1


def test_no_question_appears_twice(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[
            {"question_type": "mcq", "difficulty": None, "count": 5},
            {"question_type": "mcq", "difficulty": "easy", "count": 3},
        ],
    )
    _, entries = generate_paper(exam=exam, candidate_id=candidate.id)
    ids = [e.question_id for e in entries]
    assert len(ids) == len(set(ids))


def test_unsatisfiable_pool_raises(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "long_answer", "difficulty": None, "count": 2}],
    )
    with pytest.raises(ValidationError, match="cannot satisfy"):
        generate_paper(exam=exam, candidate_id=candidate.id)


def test_pool_check_reports_the_shortfall(db, pool):
    subject, examiner, questions = pool
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "image_upload", "difficulty": None, "count": 3}],
    )
    problems = check_pool_satisfies_rules(exam)
    assert len(problems) == 1
    assert "image_upload" in problems[0]


def test_pool_check_passes_for_a_satisfiable_exam(db, pool):
    subject, examiner, questions = pool
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "mcq", "difficulty": "medium", "count": 4}],
    )
    assert check_pool_satisfies_rules(exam) == []


def test_seed_depends_on_the_salt(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(db, subject, examiner, questions=questions)

    first = compute_seed(exam_id=exam.id, candidate_id=candidate.id, salt="salt-a")
    second = compute_seed(exam_id=exam.id, candidate_id=candidate.id, salt="salt-b")
    assert first != second


def test_option_order_is_a_permutation_of_the_real_options(db, pool):
    subject, examiner, questions = pool
    candidate = make_user(db, role=UserRole.CANDIDATE)
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "mcq", "difficulty": None, "count": 4}],
    )
    _, entries = generate_paper(exam=exam, candidate_id=candidate.id)
    by_id = {q.id: q for q in questions}

    for entry in entries:
        question = by_id[entry.question_id]
        assert sorted(str(o) for o in entry.option_order) == sorted(
            str(o.id) for o in question.options
        )
