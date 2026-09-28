"""Exam-level result reports: ownership enforcement, summary counts, and the mark-list PDF.

Reads the same data ranking/results already expose - see `test_ranking_and_results.py`'s
`_sit_and_score` helper, reused here rather than re-deriving marks.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Difficulty,
    ExamStatus,
    IntegrityVerdict,
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
from app.tests.test_ranking_and_results import _sit_and_score

API = "/api/v1"


class TestOwnershipIsEnforced:
    def _foreign_exam(self, db: Session):
        owner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, owner, questions=[question], status=ExamStatus.PUBLISHED)
        _sit_and_score(db, exam, candidate, obtained=8, total=10, correct=4, incorrect=1, unanswered=0)
        return owner, exam

    def test_ranking_refuses_a_stranger_examiner(self, client: TestClient, db: Session):
        _, exam = self._foreign_exam(db)
        stranger = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            f"{API}/exams/{exam.id}/ranking", headers=auth_headers(client, stranger)
        )
        assert response.status_code == 403

    def test_marks_sheet_refuses_a_stranger_examiner(self, client: TestClient, db: Session):
        _, exam = self._foreign_exam(db)
        stranger = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            f"{API}/exams/{exam.id}/results", headers=auth_headers(client, stranger)
        )
        assert response.status_code == 403

    def test_report_candidates_refuses_a_stranger_examiner(self, client: TestClient, db: Session):
        _, exam = self._foreign_exam(db)
        stranger = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            f"{API}/reports/exams/{exam.id}/candidates", headers=auth_headers(client, stranger)
        )
        assert response.status_code == 403

    def test_report_pdf_refuses_a_stranger_examiner(self, client: TestClient, db: Session):
        _, exam = self._foreign_exam(db)
        stranger = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            f"{API}/reports/exams/{exam.id}/pdf", headers=auth_headers(client, stranger)
        )
        assert response.status_code == 403

    def test_result_detail_refuses_a_stranger_examiner(self, client: TestClient, db: Session):
        owner, exam = self._foreign_exam(db)
        subject_result = client.get(
            f"{API}/exams/{exam.id}/ranking", headers=auth_headers(client, owner)
        ).json()[0]
        stranger = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            f"{API}/results/{subject_result['result_id']}/pdf",
            headers=auth_headers(client, stranger),
        )
        assert response.status_code == 403

    def test_admin_is_unrestricted(self, client: TestClient, db: Session):
        _, exam = self._foreign_exam(db)
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.get(
            f"{API}/reports/exams/{exam.id}/candidates", headers=auth_headers(client, admin)
        )
        assert response.status_code == 200


class TestExamReportSummary:
    def test_counts_and_marks_range_over_approved_only(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)

        approved_low = make_user(db, role=UserRole.CANDIDATE)
        approved_high = make_user(db, role=UserRole.CANDIDATE)
        flagged_pending = make_user(db, role=UserRole.CANDIDATE)
        rejected = make_user(db, role=UserRole.CANDIDATE)
        enroll(db, exam, approved_low, approved_high, flagged_pending, rejected)

        _sit_and_score(db, exam, approved_low, obtained=4, total=10, correct=2, incorrect=3, unanswered=0)
        _sit_and_score(db, exam, approved_high, obtained=9, total=10, correct=4, incorrect=1, unanswered=0)

        flagged_result = _sit_and_score(
            db, exam, flagged_pending, obtained=6, total=10, correct=3, incorrect=2, unanswered=0,
            flagged=True, suspicion=70.0,
        )
        # Flagged + still pending integrity ruling: withhold "approved" status.
        flagged_result.published = False
        flagged_result.published_at = None
        db.flush()

        rejected_result = _sit_and_score(
            db, exam, rejected, obtained=7, total=10, correct=3, incorrect=1, unanswered=1,
            flagged=True, suspicion=90.0,
        )
        rejected_result.published = False
        rejected_result.published_at = None
        rejected_result.session.integrity_verdict = IntegrityVerdict.MALPRACTICE
        db.flush()

        headers = auth_headers(client, examiner)
        response = client.get(f"{API}/reports/exams", headers=headers)
        assert response.status_code == 200, response.text
        row = next(r for r in response.json() if r["exam_id"] == str(exam.id))

        assert row["total_candidates"] == 4
        assert row["completed"] == 4
        assert row["approved"] == 2
        assert row["flagged"] == 2
        assert row["rejected"] == 1
        assert row["pending_review"] == 1
        assert row["average_marks"] == 6.5
        assert row["highest_marks"] == 9
        assert row["lowest_marks"] == 4


class TestExamMarkListPdf:
    def test_pdf_includes_only_approved_candidates(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)

        approved = make_user(db, role=UserRole.CANDIDATE)
        pending = make_user(db, role=UserRole.CANDIDATE)
        enroll(db, exam, approved, pending)

        _sit_and_score(db, exam, approved, obtained=8, total=10, correct=4, incorrect=1, unanswered=0)
        pending_result = _sit_and_score(
            db, exam, pending, obtained=5, total=10, correct=2, incorrect=3, unanswered=0
        )
        pending_result.published = False
        pending_result.published_at = None
        db.flush()

        headers = auth_headers(client, examiner)
        response = client.get(f"{API}/reports/exams/{exam.id}/pdf", headers=headers)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

        candidates_response = client.get(
            f"{API}/reports/exams/{exam.id}/candidates?sort_by=marks&order=desc", headers=headers
        )
        rows = candidates_response.json()
        assert [r["obtained_marks"] for r in rows] == [8, 5]
