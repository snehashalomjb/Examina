"""Authentication, the role matrix, and the admin access gate."""

from __future__ import annotations

import uuid

from app.core.security import create_exam_session_token, decode_exam_session_token
from app.db.models import AccessStatus, UserRole
from app.tests.conftest import TEST_PASSWORD, auth_headers, make_user


class TestRegistrationAndLogin:
    def test_candidate_registration_is_open_and_the_account_is_active(self, client):
        """Registration needs no approval: the account is created active immediately."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new.candidate@test.edu",
                "password": "Passw0rd!",
                "first_name": "New",
                "last_name": "Candidate",
                "role": "candidate",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["user"]["access_status"] == "approved"
        assert body["user"]["first_name"] == "New"
        assert body["user"]["last_name"] == "Candidate"
        assert body["user"]["full_name"] == "New Candidate"
        # The gate is the *login*, not the account.
        assert body["login_access"] == "pending"
        assert body["access_token"]

    def test_first_login_raises_a_pending_approval_request(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "first.login@test.edu",
                "password": "Passw0rd!",
                "first_name": "First",
                "last_name": "Login",
                "role": "candidate",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "first.login@test.edu", "password": "Passw0rd!"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["login_access"] == "pending"

    def test_examiner_registers_as_pending(self, client):
        """Examiner *accounts* still need an administrator - they can author and grade."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new.examiner@test.edu",
                "password": "Passw0rd!",
                "first_name": "New",
                "last_name": "Examiner",
                "role": "examiner",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["user"]["access_status"] == "pending"
        assert body["login_access"] is None

    def test_admin_cannot_self_register(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "sneaky@test.edu",
                "password": "Passw0rd!",
                "first_name": "Sneaky",
                "role": "admin",
            },
        )
        assert response.status_code == 422

    def test_duplicate_email_rejected(self, client, db):
        user = make_user(db, role=UserRole.CANDIDATE, email="dupe@test.edu")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": user.email,
                "password": "Passw0rd!",
                "first_name": "Duplicate",
                "role": "candidate",
            },
        )
        assert response.status_code == 409

    def test_weak_password_rejected(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@test.edu",
                "password": "onlyletters",
                "first_name": "Weak",
                "role": "candidate",
            },
        )
        assert response.status_code == 422

    def test_wrong_password_is_401(self, client, db):
        user = make_user(db, role=UserRole.CANDIDATE)
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "WrongPass1"}
        )
        assert response.status_code == 401

    def test_refresh_returns_a_new_access_token(self, client, db):
        user = make_user(db, role=UserRole.CANDIDATE)
        login = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        ).json()
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_me_returns_the_current_user(self, client, db):
        user = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        response = client.get("/api/v1/auth/me", headers=auth_headers(client, user))
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_no_token_is_401(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_garbage_token_is_401(self, client):
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401


class TestEditOwnProfile:
    def test_name_change_is_persisted(self, client, db):
        """The edit reaches the database, not just the response body."""
        user = make_user(db, email="editor@test.edu", role=UserRole.CANDIDATE, access=AccessStatus.APPROVED)
        headers = auth_headers(client, user)

        response = client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Renamed", "last_name": "Person"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Renamed Person"

        db.refresh(user)
        assert (user.first_name, user.last_name) == ("Renamed", "Person")
        assert user.full_name == "Renamed Person"

        # And a fresh read of the session agrees.
        assert client.get("/api/v1/auth/me", headers=headers).json()["full_name"] == (
            "Renamed Person"
        )

    def test_last_name_may_be_dropped(self, client, db):
        user = make_user(db, email="oneword@test.edu", role=UserRole.CANDIDATE, access=AccessStatus.APPROVED)
        headers = auth_headers(client, user)

        response = client.patch("/api/v1/auth/me", json={"first_name": "Solo"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Solo"

    def test_blank_first_name_is_rejected(self, client, db):
        user = make_user(db, email="blank@test.edu", role=UserRole.CANDIDATE, access=AccessStatus.APPROVED)
        response = client.patch(
            "/api/v1/auth/me",
            json={"first_name": ""},
            headers=auth_headers(client, user),
        )
        assert response.status_code == 422

    def test_edit_requires_a_token(self, client):
        assert client.patch("/api/v1/auth/me", json={"first_name": "Nobody"}).status_code == 401

    def test_role_and_email_are_not_editable(self, client, db):
        """Extra keys are ignored: the record keeps its email and role."""
        user = make_user(db, email="keeps@test.edu", role=UserRole.CANDIDATE, access=AccessStatus.APPROVED)
        response = client.patch(
            "/api/v1/auth/me",
            json={
                "first_name": "Still",
                "last_name": "Candidate",
                "email": "hijack@test.edu",
                "role": "admin",
            },
            headers=auth_headers(client, user),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == "keeps@test.edu"
        assert body["role"] == "candidate"


class TestForgotPassword:
    def test_unknown_email_still_returns_ok(self, client):
        response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@test.edu"})
        assert response.status_code == 200
        assert "If an account exists" in response.json()["detail"]

    def test_reset_flow_changes_the_password(self, client, db):
        user = make_user(db, role=UserRole.CANDIDATE)
        forgot = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        token = forgot.json()["detail"].split("reset_token=")[-1]

        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "BrandNew1"},
        )
        assert reset.status_code == 200

        assert (
            client.post(
                "/api/v1/auth/login", json={"email": user.email, "password": "BrandNew1"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
            ).status_code
            == 401
        )

    def test_bad_reset_token_rejected(self, client):
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "rubbish", "new_password": "BrandNew1"},
        )
        assert response.status_code == 400


class TestAccessGate:
    """An examiner is inert until an admin approves them."""

    def test_pending_examiner_cannot_reach_the_question_bank(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.PENDING)
        response = client.get("/api/v1/questions", headers=auth_headers(client, examiner))
        assert response.status_code == 403
        assert "awaiting administrator approval" in response.json()["detail"]

    def test_pending_examiner_cannot_create_a_question(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.PENDING)
        response = client.post(
            "/api/v1/questions",
            headers=auth_headers(client, examiner),
            json={
                "subject_id": str(uuid.uuid4()),
                "question_type": "mcq",
                "body": "Blocked?",
                "marks": 1,
                "options": [
                    {"text": "Yes", "is_correct": True},
                    {"text": "No", "is_correct": False},
                ],
            },
        )
        assert response.status_code == 403

    def test_revoked_examiner_is_told_so(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.REVOKED)
        response = client.get("/api/v1/questions", headers=auth_headers(client, examiner))
        assert response.status_code == 403
        assert "revoked" in response.json()["detail"]

    def test_approved_examiner_gets_in(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        response = client.get("/api/v1/questions", headers=auth_headers(client, examiner))
        assert response.status_code == 200

    def test_admin_grants_access_and_the_examiner_gets_in(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN, access=AccessStatus.APPROVED)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.PENDING)
        examiner_headers = auth_headers(client, examiner)

        assert client.get("/api/v1/questions", headers=examiner_headers).status_code == 403

        grant = client.patch(
            f"/api/v1/admin/users/{examiner.id}/access",
            headers=auth_headers(client, admin),
            json={"access_status": "approved", "note": "Verified faculty ID"},
        )
        assert grant.status_code == 200
        assert grant.json()["access_status"] == "approved"

        # A fresh token picks up the new status.
        assert (
            client.get("/api/v1/questions", headers=auth_headers(client, examiner)).status_code
            == 200
        )

    def test_admin_can_revoke_access_again(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)

        client.patch(
            f"/api/v1/admin/users/{examiner.id}/access",
            headers=auth_headers(client, admin),
            json={"access_status": "revoked", "note": "Contract ended"},
        )
        assert (
            client.get("/api/v1/questions", headers=auth_headers(client, examiner)).status_code
            == 403
        )

    def test_pending_candidate_cannot_list_exams(self, client, db):
        """The gate covers candidates: no approval, no exams."""
        candidate = make_user(db, role=UserRole.CANDIDATE, access=AccessStatus.PENDING)
        response = client.get("/api/v1/my/exams", headers=auth_headers(client, candidate))
        assert response.status_code == 403
        assert "awaiting administrator approval" in response.json()["detail"]

    def test_pending_candidate_cannot_start_an_exam(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE, access=AccessStatus.PENDING)
        response = client.post(
            f"/api/v1/exams/{uuid.uuid4()}/start", headers=auth_headers(client, candidate)
        )
        assert response.status_code == 403

    def test_admin_approves_a_candidate_and_they_get_in(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        candidate = make_user(db, role=UserRole.CANDIDATE, access=AccessStatus.PENDING)

        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 403
        )

        grant = client.patch(
            f"/api/v1/admin/users/{candidate.id}/access",
            headers=auth_headers(client, admin),
            json={"access_status": "approved", "note": "Enrolment verified"},
        )
        assert grant.status_code == 200

        assert (
            client.get("/api/v1/my/exams", headers=auth_headers(client, candidate)).status_code
            == 200
        )

    def test_an_examiner_cannot_approve_anyone(self, client, db):
        """Approval is administrator-only - an approved examiner is still not an admin."""
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        other_examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.PENDING)
        candidate = make_user(db, role=UserRole.CANDIDATE, access=AccessStatus.PENDING)
        headers = auth_headers(client, examiner)

        for target in (other_examiner, candidate):
            response = client.patch(
                f"/api/v1/admin/users/{target.id}/access",
                headers=headers,
                json={"access_status": "approved"},
            )
            assert response.status_code == 403

        # The examiner also cannot mint an already-approved account to sidestep the gate.
        assert (
            client.post(
                "/api/v1/admin/users",
                headers=headers,
                json={
                    "email": "backdoor@test.edu",
                    "password": "Passw0rd!",
                    "full_name": "Back Door",
                    "role": "examiner",
                    "access_status": "approved",
                },
            ).status_code
            == 403
        )

    def test_pending_users_of_both_roles_reach_the_admin_queue(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        make_user(db, role=UserRole.EXAMINER, access=AccessStatus.PENDING)
        make_user(db, role=UserRole.CANDIDATE, access=AccessStatus.PENDING)

        response = client.get("/api/v1/admin/users/pending", headers=auth_headers(client, admin))
        assert response.status_code == 200
        roles = {row["role"] for row in response.json()}
        assert {"examiner", "candidate"} <= roles

    def test_candidate_cannot_reach_the_question_bank(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = client.get("/api/v1/questions", headers=auth_headers(client, candidate))
        assert response.status_code == 403

    def test_examiner_cannot_reach_admin_routes(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        response = client.get("/api/v1/admin/users", headers=auth_headers(client, examiner))
        assert response.status_code == 403

    def test_examiner_can_see_the_candidate_roster(self, client, db):
        """Admins and examiners both need the candidate list."""
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        make_user(db, role=UserRole.CANDIDATE)
        response = client.get("/api/v1/admin/candidates", headers=auth_headers(client, examiner))
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_cannot_gate_another_admin(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        other = make_user(db, role=UserRole.ADMIN)
        response = client.patch(
            f"/api/v1/admin/users/{other.id}/access",
            headers=auth_headers(client, admin),
            json={"access_status": "revoked"},
        )
        assert response.status_code == 400

    def test_admin_cannot_change_their_own_access(self, client, db):
        admin = make_user(db, role=UserRole.ADMIN)
        response = client.patch(
            f"/api/v1/admin/users/{admin.id}/access",
            headers=auth_headers(client, admin),
            json={"access_status": "revoked"},
        )
        assert response.status_code == 400


class TestExamSessionToken:
    def test_token_round_trips(self):
        from datetime import UTC, datetime, timedelta

        session_id, exam_id, candidate_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        token = create_exam_session_token(
            session_id=session_id,
            exam_id=exam_id,
            candidate_id=candidate_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        claims = decode_exam_session_token(token)
        assert claims is not None
        assert claims.session_id == session_id
        assert claims.candidate_id == candidate_id

    def test_an_access_token_is_not_an_exam_token(self, db):
        from app.core.security import create_access_token

        access = create_access_token(
            user_id=uuid.uuid4(), role="candidate", access_status="approved"
        )
        assert decode_exam_session_token(access) is None
