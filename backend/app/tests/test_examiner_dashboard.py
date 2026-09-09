"""The examiner dashboard's summary counts, and who they are allowed to count.

Every tile answers the same question - "how much of *my* work is outstanding" - so an
examiner's totals must never include another examiner's exams, sittings or grading
backlog. An admin is the deliberate exception: platform-wide is the point of that role.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db.models import (
    Answer,
    ExamSession,
    GradeStatus,
    QuestionType,
    SessionStatus,
    UserRole,
)
from app.tests.conftest import (
    auth_headers,
    enroll,
    make_exam,
    make_question,
    make_subject,
    make_user,
)

API = "/api/v1"


def _stats(client, user) -> dict:
    response = client.get(f"{API}/examiner/stats", headers=auth_headers(client, user))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def two_examiners(db):
    """Examiner A owns an exam with a live, flagged, ungraded sitting. Examiner B owns nothing."""
    subject = make_subject(db)
    examiner_a = make_user(db, role=UserRole.EXAMINER)
    examiner_b = make_user(db, role=UserRole.EXAMINER)
    candidate = make_user(db, role=UserRole.CANDIDATE)

    questions = [
        make_question(db, subject, qtype=QuestionType.MCQ, created_by=examiner_a),
        make_question(db, subject, qtype=QuestionType.SHORT_ANSWER, created_by=examiner_a),
    ]
    exam = make_exam(
        db,
        subject,
        examiner_a,
        questions=questions,
        rules=[{"question_type": "mcq", "difficulty": "easy", "count": 1}],
    )
    enroll(db, exam, candidate)

    session = ExamSession(
        exam_id=exam.id,
        candidate_id=candidate.id,
        paper_seed="seed",
        question_order=[],
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        status=SessionStatus.IN_PROGRESS,
        is_flagged=True,
    )
    db.add(session)
    db.flush()
    db.add(
        Answer(
            session_id=session.id,
            question_id=questions[1].id,
            max_marks=5,
            grade_status=GradeStatus.AI_SCORED,
        )
    )
    db.flush()
    return examiner_a, examiner_b, candidate


class TestScoping:
    def test_the_owning_examiner_sees_their_own_work(self, client, two_examiners):
        examiner_a, _, _ = two_examiners
        stats = _stats(client, examiner_a)

        assert stats["my_exams"] == 1
        assert stats["live_sessions"] == 1
        assert stats["flagged_sessions"] == 1
        assert stats["pending_grading"] == 1
        assert stats["total_candidates"] == 1

    @pytest.mark.parametrize(
        "field",
        [
            "my_exams",
            "my_questions",
            "published_exams",
            "live_sessions",
            "flagged_sessions",
            "pending_grading",
            "active_assessments",
            "total_candidates",
        ],
    )
    def test_another_examiner_sees_none_of_it(self, client, two_examiners, field):
        # The leak this guards: B reading A's live sittings and grading backlog off
        # their own dashboard.
        _, examiner_b, _ = two_examiners
        assert _stats(client, examiner_b)[field] == 0

    def test_an_admin_sees_the_whole_platform(self, client, db, two_examiners):
        admin = make_user(db, role=UserRole.ADMIN)
        stats = _stats(client, admin)

        assert stats["my_exams"] >= 1
        assert stats["live_sessions"] >= 1
        assert stats["flagged_sessions"] >= 1
        assert stats["pending_grading"] >= 1

    def test_subjects_are_a_shared_taxonomy_not_owned_work(self, client, two_examiners):
        # Subjects are deliberately unscoped - an examiner authoring against the shared
        # taxonomy needs to see all of it, not only subjects they happened to create.
        _, examiner_b, _ = two_examiners
        assert _stats(client, examiner_b)["subjects"] >= 1


class TestCandidatesAreNotStaff:
    def test_a_candidate_cannot_read_examiner_stats(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = client.get(
            f"{API}/examiner/stats", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 403
