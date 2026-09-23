"""The randomization contract, written as the product spec states it.

Five questions in the pool. Two candidates. Both sit all five, in different orders, with
the options untouched - and neither order moves when they refresh.

`test_paper_generator.py` covers determinism at the seed level. This file is deliberately
the blunt, behavioural version: it asserts the promises an examiner is actually making to
a candidate, so a future change to the drawing logic that technically stays deterministic
but quietly drops a question still fails here.
"""

from __future__ import annotations

from collections import Counter

import pytest

from app.db.models import Difficulty, QuestionType, UserRole
from app.services.paper_generator import generate_paper
from app.tests.conftest import make_exam, make_question, make_subject, make_user

QUESTION_COUNT = 5


@pytest.fixture
def five_question_exam(db):
    """An exam whose pool is exactly the five questions every candidate must sit."""
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER)
    questions = [
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY)
        for _ in range(QUESTION_COUNT)
    ]
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        rules=[{"question_type": "mcq", "difficulty": "easy", "count": QUESTION_COUNT}],
        randomize=True,
        shuffle_options=False,
        negative_marking=False,
    )
    return exam, questions


def _order(exam, candidate_id):
    _, entries = generate_paper(exam=exam, candidate_id=candidate_id)
    return [e.question_id for e in entries]


def test_both_candidates_sit_the_same_five_questions_in_different_orders(
    db, five_question_exam
):
    exam, questions = five_question_exam
    a = make_user(db, role=UserRole.CANDIDATE)
    b = make_user(db, role=UserRole.CANDIDATE)

    order_a = _order(exam, a.id)
    order_b = _order(exam, b.id)
    expected = {q.id for q in questions}

    # Count, not just presence: five questions each, none dropped, none doubled.
    assert len(order_a) == QUESTION_COUNT
    assert len(order_b) == QUESTION_COUNT
    assert set(order_a) == expected
    assert set(order_b) == expected
    assert max(Counter(order_a).values()) == 1
    assert max(Counter(order_b).values()) == 1

    # Same five, different sequence. With 5! = 120 orderings a collision is possible but
    # rare; if this ever flakes, the seed is the thing to look at, not this assertion.
    assert order_a != order_b


def test_an_order_never_moves_however_often_it_is_regenerated(db, five_question_exam):
    """Standing in for refresh, reconnect, next/previous and resume.

    Every one of those re-derives the paper from (exam, candidate, salt), so a stable
    result here is a stable result for all of them.
    """
    exam, _ = five_question_exam
    candidate = make_user(db, role=UserRole.CANDIDATE)

    first = _order(exam, candidate.id)
    for _ in range(5):
        assert _order(exam, candidate.id) == first


def test_options_are_left_exactly_as_the_examiner_wrote_them(db, five_question_exam):
    """Question order shuffles; A/B/C/D does not, unless the separate setting says so."""
    exam, questions = five_question_exam
    by_id = {q.id: q for q in questions}
    candidate = make_user(db, role=UserRole.CANDIDATE)

    _, entries = generate_paper(exam=exam, candidate_id=candidate.id)

    for entry in entries:
        authored = [
            o.id for o in sorted(by_id[entry.question_id].options, key=lambda o: o.order_index)
        ]
        assert entry.option_order == authored


def test_marks_are_unchanged_by_randomization(db, five_question_exam):
    exam, questions = five_question_exam
    a = make_user(db, role=UserRole.CANDIDATE)
    b = make_user(db, role=UserRole.CANDIDATE)

    _, entries_a = generate_paper(exam=exam, candidate_id=a.id)
    _, entries_b = generate_paper(exam=exam, candidate_id=b.id)

    # Same total on both papers, and each question keeps the marks it was pooled with.
    assert sum(e.marks for e in entries_a) == sum(e.marks for e in entries_b)
    marks_by_question = {e.question_id: e.marks for e in entries_a}
    assert all(marks_by_question[e.question_id] == e.marks for e in entries_b)


def test_option_shuffling_is_opt_in_and_does_not_ride_on_question_randomization(
    db, five_question_exam
):
    """The two settings are independent - turning question order on must not move A/B/C/D.

    They used to be combined, which meant an examiner who wanted a different question
    order silently also got reshuffled options.
    """
    exam, questions = five_question_exam
    by_id = {q.id: q for q in questions}
    candidate = make_user(db, role=UserRole.CANDIDATE)

    assert exam.randomize is True
    assert exam.shuffle_options is False

    _, untouched = generate_paper(exam=exam, candidate_id=candidate.id)
    assert all(
        e.option_order
        == [o.id for o in sorted(by_id[e.question_id].options, key=lambda o: o.order_index)]
        for e in untouched
    )

    # Opting in is what moves them, and it moves nothing else.
    exam.shuffle_options = True
    db.flush()
    _, shuffled = generate_paper(exam=exam, candidate_id=candidate.id)

    assert [e.question_id for e in shuffled] == [e.question_id for e in untouched]
    for entry in shuffled:
        authored = {o.id for o in by_id[entry.question_id].options}
        assert set(entry.option_order) == authored, "an option was lost or invented"


def test_randomization_off_gives_everyone_the_examiners_own_order(db, five_question_exam):
    exam, questions = five_question_exam
    exam.randomize = False
    db.flush()

    a = make_user(db, role=UserRole.CANDIDATE)
    b = make_user(db, role=UserRole.CANDIDATE)

    authored = [q.id for q in questions]
    assert _order(exam, a.id) == authored
    assert _order(exam, b.id) == authored
