"""WebRTC signaling relay between a candidate's exam tab and staff watching it live.

These tests never construct a real SDP offer or ICE candidate - the relay does not care
what is inside a message, only who it is addressed to - so a small opaque payload stands
in for both. What is under test is the handshake gate (candidate vs. staff, same
two-token/one-token rules the other sockets already enforce) and the pairing logic:
a viewer learns about a candidate, a candidate learns about a viewer, and either side
leaving is announced to the other.
"""

from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.live_signal import WS_SUBPROTOCOL
from app.db.models import AccessStatus, Difficulty, QuestionType, UserRole
from app.tests.conftest import TEST_PASSWORD, make_exam, make_question, make_subject, make_user


@pytest.fixture
def scenario(db):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)

    questions = [
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY)
        for _ in range(2)
    ]
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=questions,
        candidates=[candidate],
        rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
    )
    return {"candidate": candidate, "examiner": examiner, "exam": exam}


def _login(client, user) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _sit(client, scenario) -> tuple[str, str, str]:
    access = _login(client, scenario["candidate"])
    response = client.post(
        f"/api/v1/exams/{scenario['exam'].id}/start",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200, response.text
    paper = response.json()
    return paper["session_id"], access, paper["exam_token"]


class TestBroadcastHandshake:
    def test_a_candidate_can_open_the_broadcast_socket(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-broadcast",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ):
            pass  # accepted is the assertion

    def test_no_credentials_is_refused(self, client, scenario):
        session_id, _, _ = _sit(client, scenario)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-broadcast",
                subprotocols=[WS_SUBPROTOCOL],
            ) as socket:
                socket.receive_json()

    def test_a_staff_token_cannot_broadcast(self, client, scenario):
        """Broadcasting is the candidate's exam token, not any signed-in account."""
        session_id, _, _ = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-broadcast",
                subprotocols=[WS_SUBPROTOCOL, staff_access, "not-an-exam-token"],
            ) as socket:
                socket.receive_json()


class TestViewHandshake:
    def test_staff_can_open_the_view_socket_and_receive_a_welcome(self, client, scenario):
        session_id, _, _ = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])
        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-view",
            subprotocols=[WS_SUBPROTOCOL, staff_access],
        ) as socket:
            welcome = socket.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["viewer_id"]
        assert welcome["candidate_online"] is False

    def test_a_candidate_cannot_open_the_view_socket(self, client, scenario):
        _, access, _ = _sit(client, scenario)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/v1/ws/sessions/00000000-0000-0000-0000-000000000000/live-view",
                subprotocols=[WS_SUBPROTOCOL, access],
            ) as socket:
                socket.receive_json()

    def test_no_credentials_is_refused(self, client, scenario):
        session_id, _, _ = _sit(client, scenario)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-view",
                subprotocols=[WS_SUBPROTOCOL],
            ) as socket:
                socket.receive_json()


class TestSignalingRelay:
    def test_a_viewer_who_joins_first_is_announced_to_the_candidate_once_it_connects(
        self, client, scenario
    ):
        session_id, access, exam_token = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-view",
            subprotocols=[WS_SUBPROTOCOL, staff_access],
        ) as viewer:
            welcome = viewer.receive_json()
            viewer_id = welcome["viewer_id"]

            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-broadcast",
                subprotocols=[WS_SUBPROTOCOL, access, exam_token],
            ) as candidate:
                join = candidate.receive_json()
                assert join == {"type": "viewer-join", "viewer_id": viewer_id}

                online = viewer.receive_json()
                assert online == {"type": "candidate-online"}

    def test_an_offer_from_the_candidate_reaches_only_the_named_viewer(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-broadcast",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as candidate:
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-view",
                subprotocols=[WS_SUBPROTOCOL, staff_access],
            ) as viewer:
                welcome = viewer.receive_json()
                viewer_id = welcome["viewer_id"]

                join = candidate.receive_json()
                assert join["viewer_id"] == viewer_id

                candidate.send_json({"type": "offer", "viewer_id": viewer_id, "sdp": "fake-sdp"})
                offer = viewer.receive_json()
                assert offer == {"type": "offer", "viewer_id": viewer_id, "sdp": "fake-sdp"}

    def test_an_answer_from_the_viewer_is_tagged_with_its_viewer_id(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-broadcast",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as candidate:
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-view",
                subprotocols=[WS_SUBPROTOCOL, staff_access],
            ) as viewer:
                welcome = viewer.receive_json()
                viewer_id = welcome["viewer_id"]
                candidate.receive_json()  # viewer-join

                # A viewer never has to name itself - the server stamps its own id.
                viewer.send_json({"type": "answer", "sdp": "fake-answer"})
                answer = candidate.receive_json()
                assert answer == {"type": "answer", "sdp": "fake-answer", "viewer_id": viewer_id}

    def test_the_candidate_is_told_when_a_viewer_leaves(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-broadcast",
            subprotocols=[WS_SUBPROTOCOL, access, exam_token],
        ) as candidate:
            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-view",
                subprotocols=[WS_SUBPROTOCOL, staff_access],
            ) as viewer:
                welcome = viewer.receive_json()
                viewer_id = welcome["viewer_id"]
                candidate.receive_json()  # viewer-join

            leave = candidate.receive_json()
            assert leave == {"type": "viewer-leave", "viewer_id": viewer_id}

    def test_the_viewer_is_told_when_the_candidate_goes_offline(self, client, scenario):
        session_id, access, exam_token = _sit(client, scenario)
        staff_access = _login(client, scenario["examiner"])

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}/live-view",
            subprotocols=[WS_SUBPROTOCOL, staff_access],
        ) as viewer:
            viewer.receive_json()  # welcome

            with client.websocket_connect(
                f"/api/v1/ws/sessions/{session_id}/live-broadcast",
                subprotocols=[WS_SUBPROTOCOL, access, exam_token],
            ):
                viewer.receive_json()  # candidate-online

            offline = viewer.receive_json()
            assert offline == {"type": "candidate-offline"}
