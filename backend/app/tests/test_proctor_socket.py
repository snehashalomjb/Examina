"""The WebSocket proctoring transport.

The socket is the preferred channel; ``POST /proctor/events`` remains the fallback. These
tests hold both to the same standard: the same auth rules, the same scoring, the same
termination - because a candidate must not be able to pick a softer transport.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.proctor import WS_SUBPROTOCOL
from app.db.models import AccessStatus, Difficulty, ProctorEventType, QuestionType, UserRole
from app.tests.conftest import (
    TEST_PASSWORD,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


@pytest.fixture
def scenario(db):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)
    other = make_user(db, role=UserRole.CANDIDATE)

    questions = [
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY)
        for _ in range(2)
    ]
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        candidates=[candidate, other],
        rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
    )
    return {"candidate": candidate, "other": other, "exam": exam}


def _login(client, user) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _sit(client, scenario, user=None):
    """Start a session and return (session_id, access_token, exam_token)."""
    user = user or scenario["candidate"]
    access = _login(client, user)
    response = client.post(
        f"/api/v1/exams/{scenario['exam'].id}/start",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200, response.text
    paper = response.json()
    return paper["session_id"], access, paper["exam_token"]


def _event(event_type: ProctorEventType = ProctorEventType.TAB_SWITCH) -> dict:
    return {
        "events": [
            {"event_type": event_type.value, "occurred_at": datetime.now(UTC).isoformat()}
        ]
    }


class TestHandshake:
    def test_a_valid_handshake_opens_the_socket(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_json(_event())
            assert socket.receive_json()["accepted"] == 1

    def test_no_credentials_is_refused(self, client, scenario):
        session_id, _, _ = _sit(client, scenario)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/proctor",
                subprotocols=[WS_SUBPROTOCOL],
            ) as socket:
                socket.receive_json()

    def test_a_garbage_exam_token_is_refused(self, client, scenario):
        session_id, access, _ = _sit(client, scenario)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/proctor",
                subprotocols=[WS_SUBPROTOCOL, access, "not.a.token"],
            ) as socket:
                socket.receive_json()

    def test_another_candidates_token_is_refused(self, client, scenario):
        """The same rule the HTTP routes enforce: a token is not transferable."""
        session_id, _, exam_token = _sit(client, scenario)
        intruder_access = _login(client, scenario["other"])
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/proctor",
                subprotocols=[WS_SUBPROTOCOL, intruder_access, exam_token],
            ) as socket:
                socket.receive_json()

    def test_a_token_for_a_different_session_is_refused(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        other_session_id, _, _ = _sit(client, scenario, scenario["other"])
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{other_session_id}/proctor",
                subprotocols=[WS_SUBPROTOCOL, access, exam_token],
            ) as socket:
                socket.receive_json()


class TestIngest:
    def test_events_are_scored_and_the_verdict_comes_back(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_json(_event(ProctorEventType.MULTIPLE_FACES))
            outcome = socket.receive_json()

        assert outcome["accepted"] == 1
        assert outcome["suspicion_score"] > 0
        assert any("more than one person" in w.lower() for w in outcome["warnings"])

    def test_the_score_accumulates_across_flushes(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_json(_event(ProctorEventType.TAB_SWITCH))
            first = socket.receive_json()
            socket.send_json(_event(ProctorEventType.WINDOW_BLUR))
            second = socket.receive_json()

        assert second["suspicion_score"] > first["suspicion_score"]

    def test_tab_switches_are_counted(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            for _ in range(3):
                socket.send_json(_event(ProctorEventType.TAB_SWITCH))
                outcome = socket.receive_json()

        assert outcome["tab_switch_count"] == 3

    def test_a_malformed_frame_does_not_drop_the_channel(self, client, scenario):
        """A client bug must not cost the candidate their proctoring channel."""
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_text('{"events": [{"event_type": "teleportation"}]}')
            assert socket.receive_json()["error"] == "invalid_batch"

            socket.send_json(_event())
            assert socket.receive_json()["accepted"] == 1

    def test_an_empty_batch_is_accepted_as_a_heartbeat(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_json({"events": []})
            outcome = socket.receive_json()

        assert outcome["accepted"] == 0
        assert outcome["terminated"] is False


class TestBothTransportsAgree:
    def test_a_socket_event_is_visible_to_the_http_route(self, client, scenario):
        """One score, one event log - whichever way the events arrived."""
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/proctor",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as socket:
            socket.send_json(_event(ProctorEventType.TAB_SWITCH))
            over_socket = socket.receive_json()

        over_http = client.post(
            f"/api/v1/sessions/{session_id}/proctor/events",
            headers={"Authorization": f"Bearer {access}", "X-Exam-Token": exam_token},
            json=_event(ProctorEventType.TAB_SWITCH),
        ).json()

        assert over_http["tab_switch_count"] == over_socket["tab_switch_count"] + 1
        assert over_http["suspicion_score"] > over_socket["suspicion_score"]
