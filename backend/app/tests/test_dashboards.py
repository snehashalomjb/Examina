"""The examiner's live console and the candidate's own performance analysis.

Two properties are load-bearing here.

The first is that the console tells the truth. The endpoint it replaced padded its
counts with ``max(real, 54)``, invented five candidates for the live list, and returned
a hardcoded alert feed naming people who do not exist. A quiet platform must report
zeros, because an examiner who cannot tell a real number from a decorative one cannot
use any of them.

The second is that a candidate's own analysis is built only from marks that have been
released to them. "You are weakest in Normalisation" computed over an unpublished paper
tells the candidate roughly how they did on it, before an examiner released it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Answer,
    ExamStatus,
    GradeStatus,
    ProctorEvent,
    ProctorEventType,
    ProctorSeverity,
    QuestionType,
    Result,
    SessionStatus,
    UserRole,
)
from app.services import live_operations, performance
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


def _sitting(db: Session, exam, candidate, *, status=SessionStatus.IN_PROGRESS):
    """A session row for an enrolled candidate, without going through the API."""
    from app.db.models import ExamSession

    session = ExamSession(
        exam_id=exam.id,
        candidate_id=candidate.id,
        status=status,
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=25),
        question_order=[str(eq.question_id) for eq in exam.exam_questions],
        paper_seed="seed",
    )
    if status is not SessionStatus.IN_PROGRESS:
        session.submitted_at = datetime.now(UTC)
    db.add(session)
    db.flush()
    return session


class TestTheConsoleTellsTheTruth:
    def test_a_quiet_platform_reports_zeros(self, client: TestClient, db: Session):
        """No inflation, no demo rows, no invented names."""
        examiner = make_user(db, role=UserRole.EXAMINER)

        data = live_operations.build(db, examiner)

        assert data["active_sessions_count"] == 0
        assert data["grading_queue_count"] == 0
        assert data["ai_prescored_count"] == 0
        assert data["avg_score_pct"] == 0.0
        assert data["live_sessions"] == []
        assert data["proctoring_alerts"] == []
        assert data["ai_grading_queue"] == []
        assert data["upcoming_exams"] == []
        assert data["recent_activity"] == []
        # Every signal share is 0 with nothing to measure, not an invented 91%.
        assert set(data["proctoring_signals"].values()) == {0}

    def test_active_sittings_are_counted_and_listed(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(3)],
            candidates=[candidate],
        )
        _sitting(db, exam, candidate)

        data = live_operations.build(db, examiner)
        assert data["active_sessions_count"] == 1
        assert len(data["live_sessions"]) == 1
        row = data["live_sessions"][0]
        assert row["candidate_name"] == candidate.full_name
        assert row["exam_title"] == exam.title
        assert row["total_questions"] == 3
        # A real countdown, from the session's own expiry.
        assert row["time_remaining_str"] != "00:00"

    def test_an_examiner_sees_only_their_own_exams(self, client: TestClient, db: Session):
        mine = make_user(db, role=UserRole.EXAMINER)
        theirs = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)

        their_exam = make_exam(
            db,
            subject,
            theirs,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        _sitting(db, their_exam, candidate)

        data = live_operations.build(db, mine)
        assert data["active_sessions_count"] == 0
        assert data["live_sessions"] == []

    def test_an_admin_sees_everything(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        admin = make_user(db, role=UserRole.ADMIN)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        _sitting(db, exam, candidate)

        assert live_operations.build(db, admin)["active_sessions_count"] == 1

    def test_exams_today_means_today(self, client: TestClient, db: Session):
        """It used to count every exam ever created."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(2)]

        open_now = make_exam(db, subject, examiner, questions=questions)
        finished = make_exam(db, subject, examiner, questions=questions)
        finished.starts_at = datetime.now(UTC) - timedelta(days=10)
        finished.ends_at = datetime.now(UTC) - timedelta(days=9)
        db.flush()

        data = live_operations.build(db, examiner)
        assert data["exams_today_count"] == 1
        assert open_now.id != finished.id  # both exist; only one is today's

    def test_alerts_come_from_real_events(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        session = _sitting(db, exam, candidate)
        db.add(
            ProctorEvent(
                session_id=session.id,
                event_type=ProctorEventType.MULTIPLE_FACES,
                severity=ProctorSeverity.CRITICAL,
                occurred_at=datetime.now(UTC),
                server_received_at=datetime.now(UTC),
                weight=15.0,
            )
        )
        db.flush()

        data = live_operations.build(db, examiner)
        assert len(data["proctoring_alerts"]) == 1
        alert = data["proctoring_alerts"][0]
        assert alert["candidate_name"] == candidate.full_name
        assert alert["alert_type"] == "More than one face"
        assert alert["severity"] == "rose"

    def test_info_level_events_are_not_alerts(self, client: TestClient, db: Session):
        """A window losing focus is a note in the record, not something to shout about."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        session = _sitting(db, exam, candidate)
        db.add(
            ProctorEvent(
                session_id=session.id,
                event_type=ProctorEventType.WINDOW_BLUR,
                severity=ProctorSeverity.INFO,
                occurred_at=datetime.now(UTC),
                server_received_at=datetime.now(UTC),
                weight=4.0,
            )
        )
        db.flush()

        assert live_operations.build(db, examiner)["proctoring_alerts"] == []

    def test_the_activity_feed_names_real_people_and_real_exams(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        _sitting(db, exam, candidate, status=SessionStatus.SUBMITTED)

        feed = live_operations.build(db, examiner)["recent_activity"]
        assert len(feed) == 1
        assert candidate.full_name in feed[0]["message"]
        assert exam.title in feed[0]["message"]

    def test_an_auto_submitted_paper_reads_differently_in_the_feed(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            candidates=[candidate],
        )
        _sitting(db, exam, candidate, status=SessionStatus.AUTO_SUBMITTED)

        feed = live_operations.build(db, examiner)["recent_activity"]
        assert "automatically" in feed[0]["message"]
        assert feed[0]["severity"] == "amber"

    def test_the_endpoint_is_staff_only(self, client: TestClient, db: Session):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = client.get(
            "/api/v1/analytics/live-dashboard", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 403

    def test_the_endpoint_serves_the_same_shape_the_ui_expects(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            "/api/v1/analytics/live-dashboard", headers=auth_headers(client, examiner)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {
            "active_sessions_count",
            "exams_today_count",
            "flagged_sessions_count",
            "grading_queue_count",
            "ai_prescored_count",
            "avg_score_pct",
            "live_sessions",
            "proctoring_alerts",
            "proctoring_signals",
            "score_distribution",
            "ai_grading_queue",
            "upcoming_exams",
            "recent_activity",
        }
        assert [b["bin"] for b in body["score_distribution"]] == [
            "0–20",
            "21–40",
            "41–60",
            "61–80",
            "81–100",
        ]


class TestTheCandidatesOwnAnalysis:
    def _paper(self, db: Session, *, topic: str, marks: float, awarded: float, published: bool):
        """One sat paper on one topic, published or not."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [
            make_question(db, subject, topic=topic, marks=marks) for _ in range(2)
        ]
        exam = make_exam(db, subject, examiner, questions=questions, candidates=[candidate])
        session = _sitting(db, exam, candidate, status=SessionStatus.SUBMITTED)

        for question in questions:
            db.add(
                Answer(
                    session_id=session.id,
                    question_id=question.id,
                    max_marks=marks,
                    awarded_marks=awarded,
                    grade_status=GradeStatus.AUTO_SCORED,
                )
            )
        db.add(
            Result(
                session_id=session.id,
                total_marks=marks * 2,
                obtained_marks=awarded * 2,
                percentage=round(100 * awarded / marks, 2),
                correct_count=2,
                incorrect_count=0,
                unanswered_count=0,
                pending_review_count=0,
                published=published,
                published_at=datetime.now(UTC) if published else None,
            )
        )
        db.flush()
        return candidate

    def test_an_unpublished_paper_does_not_appear_in_their_own_analysis(
        self, client: TestClient, db: Session
    ):
        """The leak this guards against is subtle: naming a weak topic from an
        unreleased paper tells the candidate roughly how they did on it."""
        candidate = self._paper(db, topic="Normalisation", marks=10, awarded=2, published=False)

        analysis = performance.analyse(db, candidate, published_only=True)
        assert analysis.topic_scores == []
        assert "Normalisation" not in analysis.weak_areas
        assert "nothing to analyse" in analysis.summary

    def test_the_examiners_view_of_the_same_candidate_does_include_it(
        self, client: TestClient, db: Session
    ):
        candidate = self._paper(db, topic="Normalisation", marks=10, awarded=2, published=False)

        analysis = performance.analyse(db, candidate, published_only=False)
        assert [s.topic for s in analysis.topic_scores] == ["Normalisation"]
        assert analysis.weak_areas == ["Normalisation"]
        # No published result, so no overall figure is quoted - 0% would read as a mark.
        assert "no overall score" in analysis.summary

    def test_a_published_paper_is_broken_down_by_topic(self, client: TestClient, db: Session):
        candidate = self._paper(db, topic="Indexing", marks=10, awarded=9, published=True)

        analysis = performance.analyse(db, candidate, published_only=True)
        assert [s.topic for s in analysis.topic_scores] == ["Indexing"]
        assert analysis.topic_scores[0].percentage == 90.0
        assert analysis.topic_scores[0].answers == 2
        assert analysis.strong_areas == ["Indexing"]

    def test_a_topic_with_one_answer_is_not_a_pattern(self, client: TestClient, db: Session):
        """One question somebody got wrong is not a weakness."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject, topic="Sharding", marks=10)
        exam = make_exam(db, subject, examiner, questions=[question], candidates=[candidate])
        session = _sitting(db, exam, candidate, status=SessionStatus.SUBMITTED)
        db.add(
            Answer(
                session_id=session.id,
                question_id=question.id,
                max_marks=10,
                awarded_marks=0,
                grade_status=GradeStatus.AUTO_SCORED,
            )
        )
        db.add(
            Result(
                session_id=session.id,
                total_marks=10,
                obtained_marks=0,
                percentage=0,
                correct_count=0,
                incorrect_count=1,
                unanswered_count=0,
                pending_review_count=0,
                published=True,
                published_at=datetime.now(UTC),
            )
        )
        db.flush()

        analysis = performance.analyse(db, candidate, published_only=True)
        assert analysis.topic_scores == []
        assert analysis.weak_areas == []
        # It says why, rather than silently showing an empty panel.
        assert "at least 2 marked answers" in analysis.summary

    def test_a_candidate_can_fetch_their_own_analysis(self, client: TestClient, db: Session):
        candidate = self._paper(db, topic="Indexing", marks=10, awarded=9, published=True)

        response = client.get(
            "/api/v1/my/performance-analysis", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["candidate_id"] == str(candidate.id)
        assert [t["topic"] for t in body["topic_scores"]] == ["Indexing"]

    def test_a_candidate_cannot_fetch_somebody_elses(self, client: TestClient, db: Session):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        other = make_user(db, role=UserRole.CANDIDATE)

        response = client.get(
            f"/api/v1/candidates/{other.id}/performance-analysis",
            headers=auth_headers(client, candidate),
        )
        assert response.status_code == 403

    def test_a_candidate_with_nothing_published_is_told_so(
        self, client: TestClient, db: Session
    ):
        candidate = make_user(db, role=UserRole.CANDIDATE)

        response = client.get(
            "/api/v1/my/performance-analysis", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["overall_percentage"] == 0.0
        assert body["topic_scores"] == []
        assert "No results have been published yet" in body["summary"]


def test_the_console_counts_a_draft_exam_as_neither_open_nor_upcoming(
    client: TestClient, db: Session
):
    """A draft is invisible to candidates, so it has no place on a live board."""
    examiner = make_user(db, role=UserRole.EXAMINER)
    subject = make_subject(db)
    make_exam(
        db,
        subject,
        examiner,
        questions=[make_question(db, subject, qtype=QuestionType.MCQ)],
        status=ExamStatus.DRAFT,
    )

    data = live_operations.build(db, examiner)
    assert data["exams_today_count"] == 0
    assert data["upcoming_exams"] == []
