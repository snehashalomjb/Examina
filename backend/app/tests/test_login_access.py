"""The login-approval workflow, and the boundaries around it.

Account state and login approval are separate axes. These tests pin both: that an active
account alone buys a candidate nothing, that approval is durable once given, that an
examiner's authority stops at their own enrolments, and that a candidate can never move
their own status.
"""

from __future__ import annotations

import uuid

from app.db.models import AccessStatus, LoginAccessStatus, UserRole
from app.tests.conftest import (
    TEST_PASSWORD,
    auth_headers,
    enroll,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


def _login(client, user):
    return client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})


def _pending_candidate(db):
    return make_user(db, role=UserRole.CANDIDATE, login_access=LoginAccessStatus.PENDING)


class TestAccountVersusLogin:
    def test_a_pending_candidate_account_is_still_active(self, client, db):
        candidate = _pending_candidate(db)
        response = _login(client, candidate)
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["access_status"] == "approved"  # the account itself is fine
        assert body["login_access"] == "pending"  # what is gated is the login

    def test_a_pending_candidate_can_read_their_own_status(self, client, db):
        candidate = _pending_candidate(db)
        response = client.get("/api/v1/auth/login-access", headers=auth_headers(client, candidate))
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    def test_a_pending_candidate_is_locked_out_of_the_platform(self, client, db):
        candidate = _pending_candidate(db)
        headers = auth_headers(client, candidate)

        for path in ("/api/v1/my/exams", "/api/v1/my/stats/summary", "/api/v1/my/results"):
            response = client.get(path, headers=headers)
            assert response.status_code == 403, path
            assert "awaiting approval" in response.json()["detail"]

    def test_a_rejected_candidate_is_told_so(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE, login_access=LoginAccessStatus.REJECTED)
        response = client.get("/api/v1/my/exams", headers=auth_headers(client, candidate))
        assert response.status_code == 403
        assert "rejected" in response.json()["detail"]

    def test_a_deactivated_account_cannot_sign_in_at_all(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        candidate.is_active = False
        db.flush()
        assert _login(client, candidate).status_code == 403


class TestReviewQueue:
    def test_admin_sees_every_request(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        _pending_candidate(db)
        _pending_candidate(db)

        response = client.get("/api/v1/login-requests", headers=auth_headers(client, admin))
        assert response.status_code == 200
        assert len(response.json()) >= 2

    def test_admin_approval_lets_the_candidate_in(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        candidate = _pending_candidate(db)
        headers = auth_headers(client, candidate)
        assert client.get("/api/v1/my/exams", headers=headers).status_code == 403

        queue = client.get(
            "/api/v1/login-requests?status=pending", headers=auth_headers(client, admin)
        ).json()
        row = next(r for r in queue if r["candidate_id"] == str(candidate.id))

        approve = client.post(
            f"/api/v1/login-requests/{row['id']}/approve",
            headers=auth_headers(client, admin),
            json={"note": "Enrolment verified"},
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 200
        )

    def test_approval_is_durable_across_logins(self, client, db):
        """Once approved, later sign-ins never re-enter the queue."""
        candidate = make_user(db, role=UserRole.CANDIDATE)  # approved by default
        first = _login(client, candidate).json()
        second = _login(client, candidate).json()
        assert first["login_access"] == "approved"
        assert second["login_access"] == "approved"

    def test_rejection_blocks_and_revocation_uses_the_same_path(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        candidate = make_user(db, role=UserRole.CANDIDATE)  # already approved
        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 200
        )

        queue = client.get("/api/v1/login-requests", headers=auth_headers(client, admin)).json()
        row = next(r for r in queue if r["candidate_id"] == str(candidate.id))

        reject = client.post(
            f"/api/v1/login-requests/{row['id']}/reject",
            headers=auth_headers(client, admin),
            json={"note": "Access revoked pending investigation"},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == "rejected"

        # Revocation bites immediately, not at some later sign-in.
        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 403
        )


class TestExaminerScope:
    def _examiner_with_exam(self, db, candidate=None):
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        questions = [make_question(db, subject) for _ in range(3)]
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=questions,
            candidates=[candidate] if candidate else None,
            rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
        )
        return examiner, exam

    def test_examiner_sees_only_their_own_candidates(self, client, db):
        mine = _pending_candidate(db)
        theirs = _pending_candidate(db)
        examiner, _ = self._examiner_with_exam(db, candidate=mine)

        rows = client.get("/api/v1/login-requests", headers=auth_headers(client, examiner)).json()
        ids = {row["candidate_id"] for row in rows}
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids

    def test_examiner_can_approve_a_candidate_in_their_exam(self, client, db):
        candidate = _pending_candidate(db)
        examiner, _ = self._examiner_with_exam(db, candidate=candidate)

        rows = client.get("/api/v1/login-requests", headers=auth_headers(client, examiner)).json()
        row = next(r for r in rows if r["candidate_id"] == str(candidate.id))
        assert row["enrolled_exams"], "the exam linking them should be shown as the basis"

        response = client.post(
            f"/api/v1/login-requests/{row['id']}/approve",
            headers=auth_headers(client, examiner),
            json={"note": "Enrolled in my paper"},
        )
        assert response.status_code == 200
        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 200
        )

    def test_examiner_cannot_approve_outside_their_scope(self, client, db):
        outsider = _pending_candidate(db)
        admin = make_user(db, role=UserRole.ADMIN)
        examiner, _ = self._examiner_with_exam(db)  # no candidates enrolled

        rows = client.get("/api/v1/login-requests", headers=auth_headers(client, admin)).json()
        row = next(r for r in rows if r["candidate_id"] == str(outsider.id))

        response = client.post(
            f"/api/v1/login-requests/{row['id']}/approve",
            headers=auth_headers(client, examiner),
            json={},
        )
        assert response.status_code == 403
        assert "not enrolled in any of your exams" in response.json()["detail"]

        # And the refusal is real - the candidate is still locked out.
        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, outsider)).status_code
            == 403
        )


class TestCandidatesCannotEscalate:
    def test_a_candidate_cannot_read_the_review_queue(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        assert (
            client.get(
                "/api/v1/login-requests", headers=auth_headers(client, candidate)
            ).status_code
            == 403
        )

    def test_a_candidate_cannot_approve_themselves(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        candidate = _pending_candidate(db)

        rows = client.get("/api/v1/login-requests", headers=auth_headers(client, admin)).json()
        row = next(r for r in rows if r["candidate_id"] == str(candidate.id))

        response = client.post(
            f"/api/v1/login-requests/{row['id']}/approve",
            headers=auth_headers(client, candidate),
            json={},
        )
        assert response.status_code == 403
        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 403
        )

    def test_a_candidate_cannot_change_their_access_status(self, client, db):
        candidate = _pending_candidate(db)
        response = client.patch(
            f"/api/v1/admin/users/{candidate.id}/access",
            headers=auth_headers(client, candidate),
            json={"access_status": "approved"},
        )
        assert response.status_code == 403

    def test_a_candidate_cannot_enrol_themselves(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(2)],
            rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
        )
        response = client.post(
            f"/api/v1/exams/{exam.id}/enrollments",
            headers=auth_headers(client, candidate),
            json={"candidate_ids": [str(candidate.id)]},
        )
        assert response.status_code == 403


class TestEnrolmentGatesExams:
    def _exam(self, db, examiner):
        subject = make_subject(db)
        return make_exam(
            db,
            subject,
            examiner,
            questions=[make_question(db, subject) for _ in range(3)],
            rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
        )

    def test_an_unenrolled_candidate_sees_no_exams(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        self._exam(db, examiner)
        candidate = make_user(db, role=UserRole.CANDIDATE)

        response = client.get("/api/v1/my/exams", headers=auth_headers(client, candidate))
        assert response.status_code == 200
        assert response.json() == []

    def test_knowing_the_exam_id_is_not_access(self, client, db):
        """Approved login is not permission to sit every paper on the platform."""
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = self._exam(db, examiner)
        candidate = make_user(db, role=UserRole.CANDIDATE)

        response = client.post(
            f"/api/v1/exams/{exam.id}/start", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 403
        assert "not enrolled" in response.json()["detail"]

    def test_enrolment_makes_the_exam_visible_and_startable(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = self._exam(db, examiner)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        headers = auth_headers(client, candidate)

        assert client.get("/api/v1/my/exams", headers=headers).json() == []

        response = client.post(
            f"/api/v1/exams/{exam.id}/enrollments",
            headers=auth_headers(client, examiner),
            json={"candidate_ids": [str(candidate.id)]},
        )
        assert response.status_code == 200

        cards = client.get("/api/v1/my/exams", headers=headers).json()
        assert len(cards) == 1
        assert cards[0]["exam_id"] == str(exam.id)
        assert client.post(f"/api/v1/exams/{exam.id}/start", headers=headers).status_code == 200

    def test_enrolling_twice_is_harmless(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = self._exam(db, examiner)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        headers = auth_headers(client, examiner)
        body = {"candidate_ids": [str(candidate.id)]}

        assert (
            client.post(
                f"/api/v1/exams/{exam.id}/enrollments", headers=headers, json=body
            ).status_code
            == 200
        )
        second = client.post(f"/api/v1/exams/{exam.id}/enrollments", headers=headers, json=body)
        assert second.status_code == 200
        assert "already enrolled" in second.json()["detail"]

    def test_a_candidate_who_has_sat_cannot_be_unenrolled(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = self._exam(db, examiner)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        enroll(db, exam, candidate)

        client.post(f"/api/v1/exams/{exam.id}/start", headers=auth_headers(client, candidate))

        response = client.delete(
            f"/api/v1/exams/{exam.id}/enrollments/{candidate.id}",
            headers=auth_headers(client, examiner),
        )
        assert response.status_code == 409

    def test_enrolling_a_non_candidate_is_rejected(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = self._exam(db, examiner)
        other_examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)

        response = client.post(
            f"/api/v1/exams/{exam.id}/enrollments",
            headers=auth_headers(client, examiner),
            json={"candidate_ids": [str(other_examiner.id)]},
        )
        assert response.status_code == 404


def test_unknown_login_request_is_404(client, db):
    admin = make_user(db, role=UserRole.ADMIN)
    response = client.post(
        f"/api/v1/login-requests/{uuid.uuid4()}/approve",
        headers=auth_headers(client, admin),
        json={},
    )
    assert response.status_code == 404
