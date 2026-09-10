"""Leaving the exam window: warn, final warning, auto-submit.

The rule that matters most here is the one about *what kind* of ending this is. A
candidate whose paper is submitted for them has still sat the exam: the answers are
scored, the subjective half is queued, a result exists, and an examiner rules on the
conduct afterwards. Auto-submitting is not a finding of malpractice, and these tests
exist so nobody can quietly turn it into one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Answer,
    ExamSession,
    GradeStatus,
    IntegrityVerdict,
    ProctorEvent,
    ProctorEventType,
    ProctorSeverity,
    QuestionType,
    Result,
    SessionStatus,
    UserRole,
)
from app.services.suspicion import score_events
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


def _event(
    event_type: ProctorEventType, severity: ProctorSeverity = ProctorSeverity.WARNING
) -> ProctorEvent:
    """An unsaved event, for exercising the scorer without a database."""
    return ProctorEvent(
        event_type=event_type, severity=severity, occurred_at=datetime.now(UTC)
    )


def _start(client: TestClient, exam, candidate) -> tuple[str, dict]:
    """Start a sitting and return (session_id, headers carrying the exam token)."""
    response = client.post(
        f"/api/v1/exams/{exam.id}/start", headers=auth_headers(client, candidate)
    )
    assert response.status_code in (200, 201), response.text
    body = response.json()
    headers = auth_headers(client, candidate)
    headers["X-Exam-Token"] = body["exam_token"]
    return body["session_id"], headers


def _leave(client: TestClient, session_id: str, headers: dict, kind="tab_switch") -> dict:
    """Report one "candidate left the exam" event."""
    response = client.post(
        f"/api/v1/sessions/{session_id}/proctor/events",
        json={
            "events": [
                {
                    "event_type": kind,
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "severity": "warning",
                }
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestTheLadder:
    def test_first_violation_warns_and_the_exam_continues(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(2)]
        exam = make_exam(db, subject, examiner, questions=questions, candidates=[candidate])
        session_id, headers = _start(client, exam, candidate)

        outcome = _leave(client, session_id, headers)
        assert outcome["auto_submitted"] is False
        assert outcome["focus_violation_count"] == 1
        assert outcome["focus_violations_left"] == 2
        assert any("Warning 1 of 3" in w for w in outcome["warnings"])

    def test_the_step_before_the_last_says_final_warning(self, client: TestClient, db: Session):
        """A candidate about to lose their sitting is told on the step before."""
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
        session_id, headers = _start(client, exam, candidate)

        _leave(client, session_id, headers)
        outcome = _leave(client, session_id, headers)
        assert outcome["auto_submitted"] is False
        assert outcome["focus_violations_left"] == 1
        assert any("Final warning" in w for w in outcome["warnings"])

    def test_the_limit_submits_the_paper_and_closes_the_exam(
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
        session_id, headers = _start(client, exam, candidate)

        for _ in range(2):
            _leave(client, session_id, headers)
        outcome = _leave(client, session_id, headers)

        assert outcome["auto_submitted"] is True
        assert outcome["terminated"] is False
        assert any("submitted" in w.lower() for w in outcome["warnings"])

        db.expire_all()
        session = db.get(ExamSession, session_id)
        assert session.status is SessionStatus.AUTO_SUBMITTED
        assert session.submitted_at is not None
        assert "left the exam window 3 times" in session.termination_reason

    def test_fullscreen_exits_count_towards_the_same_limit(
        self, client: TestClient, db: Session
    ):
        """Switching tab and leaving fullscreen are the same offence: leaving the exam."""
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
        session_id, headers = _start(client, exam, candidate)

        _leave(client, session_id, headers, kind="fullscreen_exit")
        _leave(client, session_id, headers, kind="tab_switch")
        outcome = _leave(client, session_id, headers, kind="fullscreen_exit")
        assert outcome["auto_submitted"] is True

    def test_a_closed_session_is_not_submitted_twice(self, client: TestClient, db: Session):
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
        session_id, headers = _start(client, exam, candidate)
        for _ in range(3):
            _leave(client, session_id, headers)

        db.expire_all()
        first_submitted_at = db.get(ExamSession, session_id).submitted_at

        # More events still land - they are evidence - but change nothing.
        outcome = _leave(client, session_id, headers)
        assert outcome["auto_submitted"] is False
        db.expire_all()
        assert db.get(ExamSession, session_id).submitted_at == first_submitted_at
        assert db.get(ExamSession, session_id).focus_violation_count == 4


class TestItIsASubmissionNotAVerdict:
    def _sit_and_walk_away(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        mcq = make_question(db, subject, correct_indices=[1], marks=4)
        written = make_question(
            db, subject, qtype=QuestionType.LONG_ANSWER, marks=6, option_count=0
        )
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[mcq, written],
            candidates=[candidate],
            rules=[
                {"question_type": "mcq", "difficulty": "easy", "count": 1},
                {"question_type": "long_answer", "difficulty": "easy", "count": 1},
            ],
        )
        session_id, headers = _start(client, exam, candidate)

        # Answer both, correctly, then walk out three times.
        correct_option = next(o.id for o in mcq.options if o.is_correct)
        client.put(
            f"/api/v1/sessions/{session_id}/answers/{mcq.id}",
            json={"selected_option_ids": [str(correct_option)]},
            headers=headers,
        )
        client.put(
            f"/api/v1/sessions/{session_id}/answers/{written.id}",
            json={"text_answer": "A considered answer about the topic at hand."},
            headers=headers,
        )
        for _ in range(3):
            _leave(client, session_id, headers)
        return examiner, candidate, exam, session_id, mcq, written

    def test_the_answers_that_were_saved_are_marked(self, client: TestClient, db: Session):
        _, _, _, session_id, mcq, _ = self._sit_and_walk_away(client, db)
        db.expire_all()

        answers = list(db.scalars(select(Answer).where(Answer.session_id == session_id)))
        by_question = {a.question_id: a for a in answers}
        assert by_question[mcq.id].grade_status is GradeStatus.AUTO_SCORED
        assert by_question[mcq.id].awarded_marks == 4

    def test_the_written_half_is_queued_for_the_examiner(self, client: TestClient, db: Session):
        _, _, _, session_id, _, written = self._sit_and_walk_away(client, db)
        db.expire_all()

        answer = db.scalar(
            select(Answer).where(
                Answer.session_id == session_id, Answer.question_id == written.id
            )
        )
        assert answer.grade_status is GradeStatus.PENDING_AI

    def test_a_result_exists_and_carries_the_objective_marks(
        self, client: TestClient, db: Session
    ):
        _, _, _, session_id, _, _ = self._sit_and_walk_away(client, db)
        db.expire_all()

        result = db.scalar(select(Result).where(Result.session_id == session_id))
        assert result is not None
        assert result.obtained_marks == 4
        assert result.pending_review_count == 1
        # Unpublished: a result exists, and releasing it is still the examiner's move.
        assert result.published is False

    def test_the_sitting_is_flagged_but_no_verdict_is_recorded(
        self, client: TestClient, db: Session
    ):
        """AI flags. The examiner rules. Nothing here pre-empts that."""
        _, _, _, session_id, _, _ = self._sit_and_walk_away(client, db)
        db.expire_all()

        session = db.get(ExamSession, session_id)
        assert session.is_flagged is True
        assert session.integrity_verdict is IntegrityVerdict.PENDING

    def test_the_examiner_can_clear_it_and_publish_the_result(
        self, client: TestClient, db: Session
    ):
        """The point of the whole design: a genuine candidate keeps their marks."""
        examiner, candidate, _, session_id, _, _ = self._sit_and_walk_away(client, db)
        staff = auth_headers(client, examiner)

        # An auto-submitted paper with a written answer still needs grading before it
        # can be published, so score it as the examiner would.
        db.expire_all()
        pending = db.scalar(
            select(Answer).where(
                Answer.session_id == session_id, Answer.grade_status == GradeStatus.PENDING_AI
            )
        )
        scored = client.post(
            f"/api/v1/grading/answers/{pending.id}/score",
            json={"awarded_marks": 5, "comment": "Reasonable answer."},
            headers=staff,
        )
        assert scored.status_code == 200, scored.text

        ruled = client.post(
            f"/api/v1/proctoring/sessions/{session_id}/integrity",
            json={"verdict": "cleared", "note": "Wi-Fi dropped; work is their own."},
            headers=staff,
        )
        assert ruled.status_code == 200, ruled.text

        published = client.post(
            f"/api/v1/sessions/{session_id}/result/publish", headers=staff
        )
        assert published.status_code == 200, published.text

        db.expire_all()
        result = db.scalar(select(Result).where(Result.session_id == session_id))
        assert result.published is True
        assert result.obtained_marks == 9  # 4 objective + 5 awarded


class TestTheExaminerCanSeeIt:
    def test_the_violation_count_is_on_the_monitoring_row(self, client: TestClient, db: Session):
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
        session_id, headers = _start(client, exam, candidate)
        _leave(client, session_id, headers, kind="fullscreen_exit")
        _leave(client, session_id, headers, kind="tab_switch")

        staff = auth_headers(client, examiner)
        rows = client.get("/api/v1/proctoring/sessions", headers=staff).json()
        row = next(r for r in rows if r["session_id"] == session_id)
        assert row["focus_violation_count"] == 2
        assert row["tab_switch_count"] == 1  # only one of the two was a tab switch

        detail = client.get(f"/api/v1/proctoring/sessions/{session_id}", headers=staff).json()
        assert detail["focus_violation_count"] == 2
        assert {e["event_type"] for e in detail["events"]} == {"fullscreen_exit", "tab_switch"}

    def test_the_heartbeat_reports_the_count_so_a_reload_cannot_reset_it(
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
        session_id, headers = _start(client, exam, candidate)
        _leave(client, session_id, headers)

        beat = client.post(f"/api/v1/sessions/{session_id}/heartbeat", headers=headers)
        assert beat.status_code == 200, beat.text
        assert beat.json()["focus_violation_count"] == 1
        assert beat.json()["focus_violations_left"] == 2


class TestConfigurability:
    def test_a_limit_of_zero_records_without_closing_the_exam(
        self, client: TestClient, db: Session
    ):
        """An open-book take-home wants the record, not the guillotine."""
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
        exam.proctor_config = {**exam.proctor_config, "max_focus_violations": 0}
        db.flush()

        session_id, headers = _start(client, exam, candidate)
        for _ in range(5):
            outcome = _leave(client, session_id, headers)

        assert outcome["auto_submitted"] is False
        assert outcome["focus_violations_left"] == -1
        db.expire_all()
        session = db.get(ExamSession, session_id)
        assert session.status is SessionStatus.IN_PROGRESS
        assert session.focus_violation_count == 5

    def test_a_stricter_limit_is_honoured(self, client: TestClient, db: Session):
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
        exam.proctor_config = {**exam.proctor_config, "max_focus_violations": 1}
        db.flush()

        session_id, headers = _start(client, exam, candidate)
        outcome = _leave(client, session_id, headers)
        assert outcome["auto_submitted"] is True


class TestWhatDoesNotCount:
    def test_window_blur_alone_never_submits_a_paper(self, client: TestClient, db: Session):
        """Blur fires for notifications, on-screen keyboards, and window managers
        being window managers. Counting it would end honest sittings."""
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
        session_id, headers = _start(client, exam, candidate)

        for _ in range(8):
            outcome = _leave(client, session_id, headers, kind="window_blur")

        assert outcome["focus_violation_count"] == 0
        assert outcome["auto_submitted"] is False
        db.expire_all()
        assert db.get(ExamSession, session_id).status is SessionStatus.IN_PROGRESS

    def test_a_flickering_webcam_never_submits_a_paper(self, client: TestClient, db: Session):
        """The vision signals are noisy by nature and stay on the score, not the ladder."""
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
        session_id, headers = _start(client, exam, candidate)

        for _ in range(10):
            outcome = _leave(client, session_id, headers, kind="face_missing")

        assert outcome["auto_submitted"] is False
        assert outcome["focus_violation_count"] == 0


class TestScoringUnit:
    def test_the_outcome_counts_both_kinds_and_leaves_a_remainder(self, db: Session):
        events = [
            _event(ProctorEventType.TAB_SWITCH),
            _event(ProctorEventType.FULLSCREEN_EXIT),
            _event(ProctorEventType.WINDOW_BLUR, ProctorSeverity.INFO),
        ]
        outcome = score_events(events, {"max_focus_violations": 3})
        assert outcome.focus_violation_count == 2
        assert outcome.focus_violations_left == 1
        assert outcome.should_auto_submit is False

    def test_reaching_the_limit_flags_as_well_as_submits(self, db: Session):
        """The examiner has to be told to look at it, not just that it ended."""
        events = [_event(ProctorEventType.TAB_SWITCH) for _ in range(3)]
        outcome = score_events(events, {"max_focus_violations": 3})
        assert outcome.should_auto_submit is True
        assert outcome.should_flag is True
