"""The examiner's integrity ruling, and the gate it puts in front of publishing.

The principle these tests encode: proctoring produces signals, a human produces verdicts.
A flagged sitting is never auto-failed and never auto-published - an examiner has to look
at the evidence and say which it was. A genuine candidate's paper is then graded and
released like any other; a sitting ruled malpractice keeps its marks on file but never
shows the candidate a grade.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.models import (
    AccessStatus,
    Difficulty,
    IntegrityVerdict,
    QuestionType,
    UserRole,
)
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)

API = "/api/v1"


@pytest.fixture
def sat_exam(client, db):
    """One candidate who has sat and submitted a purely objective paper.

    Objective-only so nothing is left pending examiner review - that gate is covered
    elsewhere, and here it would mask the integrity gate under test.
    """
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)

    mcqs = [
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY, marks=2.0)
        for _ in range(2)
    ]
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=mcqs,
        candidates=[candidate],
        rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
    )

    candidate_headers = auth_headers(client, candidate)
    started = client.post(f"{API}/exams/{exam.id}/start", headers=candidate_headers)
    assert started.status_code == 200, started.text
    paper = started.json()
    exam_headers = {**candidate_headers, "X-Exam-Token": paper["exam_token"]}

    questions = {q.id: q for q in mcqs}
    for item in paper["questions"]:
        question = questions[uuid.UUID(item["question_id"])]
        correct = [str(o.id) for o in question.options if o.is_correct]
        client.put(
            f"{API}/sessions/{paper['session_id']}/answers/{item['question_id']}",
            headers=exam_headers,
            json={"selected_option_ids": correct},
        )
    submitted = client.post(f"{API}/sessions/{paper['session_id']}/submit", headers=exam_headers)
    assert submitted.status_code == 200, submitted.text

    from app.db.models import ExamSession

    session = db.get(ExamSession, uuid.UUID(paper["session_id"]))
    return {
        "exam": exam,
        "examiner": examiner,
        "candidate": candidate,
        "session": session,
        "session_id": paper["session_id"],
        "staff_headers": auth_headers(client, examiner),
        "candidate_headers": candidate_headers,
    }


def _flag(db, session):
    session.is_flagged = True
    db.flush()


def _rule(client, sat, verdict: str, note: str | None = None):
    payload: dict = {"verdict": verdict}
    if note is not None:
        payload["note"] = note
    return client.post(
        f"{API}/proctoring/sessions/{sat['session_id']}/integrity",
        headers=sat["staff_headers"],
        json=payload,
    )


def _publish_one(client, sat):
    return client.post(
        f"{API}/sessions/{sat['session_id']}/result/publish", headers=sat["staff_headers"]
    )


class TestTheGate:
    def test_an_unflagged_sitting_publishes_without_a_ruling(self, client, sat_exam):
        # Demanding a ruling on every clean paper would turn the safeguard into a rubber
        # stamp, which is how safeguards stop being read.
        assert _publish_one(client, sat_exam).status_code == 200

    def test_a_flagged_sitting_is_blocked_until_someone_rules_on_it(
        self, client, db, sat_exam
    ):
        _flag(db, sat_exam["session"])
        response = _publish_one(client, sat_exam)
        assert response.status_code == 409
        assert "flagged" in response.text.lower()

    def test_clearing_a_flagged_sitting_lets_the_result_out(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "cleared").status_code == 200
        assert _publish_one(client, sat_exam).status_code == 200

    def test_a_sitting_ruled_malpractice_never_publishes(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "malpractice", "Two faces on camera").status_code == 200

        response = _publish_one(client, sat_exam)
        assert response.status_code == 409
        assert "malpractice" in response.text.lower()

    def test_a_live_sitting_cannot_be_ruled_on(self, client, db, sat_exam):
        from app.db.models import SessionStatus

        sat_exam["session"].status = SessionStatus.IN_PROGRESS
        db.flush()
        response = _rule(client, sat_exam, "cleared")
        assert response.status_code == 409
        assert "in progress" in response.text.lower()


class TestTheRulingItself:
    def test_malpractice_requires_a_reason(self, client, db, sat_exam):
        # A ruling that costs a candidate their result must be reviewable afterwards.
        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "malpractice").status_code == 422
        assert _rule(client, sat_exam, "malpractice", "   ").status_code == 422

    def test_clearing_needs_no_reason(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "cleared").status_code == 200

    def test_a_sitting_cannot_be_ruled_back_to_pending(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "pending").status_code == 422

    def test_the_ruling_records_who_decided_and_when(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        body = _rule(client, sat_exam, "malpractice", "Phone visible at 14:02").json()

        assert body["integrity_verdict"] == "malpractice"
        assert body["integrity_note"] == "Phone visible at 14:02"
        assert body["integrity_reviewed_by"] == sat_exam["examiner"].full_name
        assert body["integrity_reviewed_at"] is not None
        assert body["needs_integrity_review"] is False

    def test_an_unreviewed_flagged_sitting_advertises_that_it_needs_review(
        self, client, db, sat_exam
    ):
        _flag(db, sat_exam["session"])
        review = client.get(
            f"{API}/proctoring/sessions/{sat_exam['session_id']}",
            headers=sat_exam["staff_headers"],
        )
        assert review.status_code == 200
        assert review.json()["needs_integrity_review"] is True
        assert review.json()["integrity_verdict"] == IntegrityVerdict.PENDING.value

    def test_a_candidate_cannot_rule_on_their_own_sitting(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        response = client.post(
            f"{API}/proctoring/sessions/{sat_exam['session_id']}/integrity",
            headers=sat_exam["candidate_headers"],
            json={"verdict": "cleared"},
        )
        assert response.status_code == 403


class TestMalpracticeWithholdsAnAlreadyPublishedResult:
    def test_ruling_malpractice_retracts_a_published_result(self, client, db, sat_exam):
        assert _publish_one(client, sat_exam).status_code == 200
        assert client.get(f"{API}/my/results", headers=sat_exam["candidate_headers"]).json()

        _flag(db, sat_exam["session"])
        assert _rule(client, sat_exam, "malpractice", "Reviewed after release").status_code == 200

        # The marks still exist for an appeal; the candidate simply no longer sees a grade.
        assert client.get(f"{API}/my/results", headers=sat_exam["candidate_headers"]).json() == []


class TestBulkPublish:
    def _publish_exam(self, client, sat):
        return client.post(
            f"{API}/exams/{sat['exam'].id}/results/publish", headers=sat["staff_headers"]
        )

    def test_bulk_publish_refuses_while_a_flagged_sitting_is_unreviewed(
        self, client, db, sat_exam
    ):
        _flag(db, sat_exam["session"])
        response = self._publish_exam(client, sat_exam)
        assert response.status_code == 409
        assert "integrity ruling" in response.text.lower()

    def test_bulk_publish_skips_sittings_ruled_malpractice(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        _rule(client, sat_exam, "malpractice", "Multiple faces throughout")

        response = self._publish_exam(client, sat_exam)
        assert response.status_code == 200
        assert "withheld 1" in response.json()["detail"]
        # And the candidate still sees nothing.
        assert client.get(f"{API}/my/results", headers=sat_exam["candidate_headers"]).json() == []

    def test_bulk_publish_releases_a_cleared_sitting(self, client, db, sat_exam):
        _flag(db, sat_exam["session"])
        _rule(client, sat_exam, "cleared", "Sibling walked past once")

        assert self._publish_exam(client, sat_exam).status_code == 200
        assert client.get(f"{API}/my/results", headers=sat_exam["candidate_headers"]).json()


class TestPublishRecordsTheApprover:
    def test_the_publishing_examiner_is_recorded(self, client, db, sat_exam):
        assert _publish_one(client, sat_exam).status_code == 200

        db.expire_all()
        from app.db.models import ExamSession

        session = db.get(ExamSession, uuid.UUID(sat_exam["session_id"]))
        assert session.result.published_by_id == sat_exam["examiner"].id
        assert session.result.published_at is not None
