"""The examiner's per-candidate results table.

Used to require a corporate exam - "ranking" was corporate-only, and an academic
examiner had no equivalent screen at all: no scores, no flags, no attempt counts for
any exam that was not a hiring assessment. These tests cover the two things that
changed: the table itself is now available for any exam, and the parts that are
genuinely a hiring decision - shortlisting - are still refused for one that is not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Difficulty,
    Exam,
    ExamSession,
    ExamStatus,
    Result,
    SessionStatus,
    UserRole,
)
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


def _sit_and_score(
    db: Session,
    exam: Exam,
    candidate,
    *,
    obtained: float,
    total: float,
    correct: int,
    incorrect: int,
    unanswered: int,
    flagged: bool = False,
    suspicion: float = 0.0,
) -> Result:
    """Build a completed, scored sitting directly - the ranking table only reads it."""
    now = datetime.now(UTC)
    session = ExamSession(
        exam_id=exam.id,
        candidate_id=candidate.id,
        paper_seed="test-seed",
        question_order=[],
        started_at=now - timedelta(minutes=20),
        expires_at=now + timedelta(minutes=10),
        submitted_at=now,
        status=SessionStatus.SUBMITTED,
        is_flagged=flagged,
        suspicion_score=suspicion,
    )
    db.add(session)
    db.flush()

    result = Result(
        session_id=session.id,
        total_marks=total,
        obtained_marks=obtained,
        percentage=round(obtained / total * 100, 2) if total else 0.0,
        correct_count=correct,
        incorrect_count=incorrect,
        unanswered_count=unanswered,
        published=True,
        published_at=now,
    )
    db.add(result)
    db.flush()
    return result


class TestResultsAreOpenToAnyExam:
    def test_an_academic_exam_has_a_results_table_too(self, client: TestClient, db: Session):
        """The bug: ranking used to 400 on anything that was not corporate."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)
        headers = auth_headers(client, examiner)

        _sit_and_score(
            db, exam, candidate, obtained=8, total=10, correct=4, incorrect=1, unanswered=0
        )

        response = client.get(f"/api/v1/exams/{exam.id}/ranking", headers=headers)

        assert response.status_code == 200, response.text
        row = response.json()[0]
        assert row["full_name"] == candidate.full_name
        assert row["obtained_marks"] == 8
        assert row["correct_count"] == 4

    def test_shows_score_flags_and_questions_attempted(self, client: TestClient, db: Session):
        """The three things an examiner asked for: score, flags, attempted."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)
        headers = auth_headers(client, examiner)

        _sit_and_score(
            db,
            exam,
            candidate,
            obtained=6,
            total=10,
            correct=3,
            incorrect=2,
            unanswered=1,
            flagged=True,
            suspicion=62.0,
        )

        row = client.get(f"/api/v1/exams/{exam.id}/ranking", headers=headers).json()[0]

        assert row["overall_percentage"] == 60.0
        assert row["is_flagged"] is True
        assert row["suspicion_score"] == 62.0
        assert row["correct_count"] + row["incorrect_count"] == 5, "questions attempted"
        assert row["unanswered_count"] == 1

    def test_an_unpublished_paper_has_no_row_yet(self, client: TestClient, db: Session):
        """Unpublished means not yet an examiner-approved score - nothing to rank."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)
        headers = auth_headers(client, examiner)

        now = datetime.now(UTC)
        db.add(
            ExamSession(
                exam_id=exam.id,
                candidate_id=candidate.id,
                paper_seed="s",
                question_order=[],
                started_at=now - timedelta(minutes=10),
                expires_at=now + timedelta(minutes=10),
                submitted_at=now,
                status=SessionStatus.SUBMITTED,
            )
        )
        db.flush()

        response = client.get(f"/api/v1/exams/{exam.id}/ranking", headers=headers)

        assert response.status_code == 200
        assert response.json() == []


class TestShortlistingStaysCorporateOnly:
    def test_shortlisting_an_academic_exam_is_refused(self, client: TestClient, db: Session):
        """Deciding to hire someone is a corporate action; viewing their score is not."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.PUBLISHED)
        headers = auth_headers(client, examiner)

        response = client.post(
            f"/api/v1/exams/{exam.id}/shortlist",
            json={"decisions": [{"candidate_id": str(candidate.id), "status": "shortlisted"}]},
            headers=headers,
        )

        assert response.status_code == 400

    def test_listing_shortlists_on_an_academic_exam_is_refused(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.PUBLISHED)
        headers = auth_headers(client, examiner)

        response = client.get(f"/api/v1/exams/{exam.id}/shortlists", headers=headers)

        assert response.status_code == 400

    def test_a_corporate_exam_can_still_be_shortlisted(self, client: TestClient, db: Session):
        """The gate is real, not a stub - a genuine corporate exam still works."""
        from app.db.models import ExamType

        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.PUBLISHED)
        exam.exam_type = ExamType.CORPORATE
        db.flush()
        headers = auth_headers(client, examiner)

        response = client.post(
            f"/api/v1/exams/{exam.id}/shortlist",
            json={"decisions": [{"candidate_id": str(candidate.id), "status": "shortlisted"}]},
            headers=headers,
        )

        assert response.status_code == 200, response.text
