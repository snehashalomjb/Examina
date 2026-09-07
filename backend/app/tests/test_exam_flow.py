"""End-to-end: start -> answer -> proctor events -> submit -> grade -> review -> publish."""

from __future__ import annotations

import uuid

import pytest

from app.db.models import (
    AccessStatus,
    Difficulty,
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


@pytest.fixture
def scenario(db):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)

    mcqs = [
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY, marks=2.0)
        for _ in range(3)
    ]
    multi = make_question(
        db,
        subject,
        qtype=QuestionType.MULTI_SELECT,
        difficulty=Difficulty.MEDIUM,
        marks=4.0,
        correct_indices=[0, 1],
    )
    short = make_question(
        db, subject, qtype=QuestionType.SHORT_ANSWER, difficulty=Difficulty.MEDIUM, marks=5.0
    )

    exam = make_exam(
        db,
        subject,
        examiner,
        questions=[*mcqs, multi, short],
        candidates=[candidate],
        rules=[
            {"question_type": "mcq", "difficulty": "easy", "count": 2},
            {"question_type": "multi_select", "difficulty": None, "count": 1},
            {"question_type": "short_answer", "difficulty": None, "count": 1},
        ],
    )
    return {
        "subject": subject,
        "examiner": examiner,
        "candidate": candidate,
        "exam": exam,
        "questions": {q.id: q for q in [*mcqs, multi, short]},
    }


def _start(client, scenario):
    headers = auth_headers(client, scenario["candidate"])
    response = client.post(f"/api/v1/exams/{scenario['exam'].id}/start", headers=headers)
    assert response.status_code == 200, response.text
    paper = response.json()
    exam_headers = {**headers, "X-Exam-Token": paper["exam_token"]}
    return paper, headers, exam_headers


class TestStart:
    def test_candidate_starts_and_receives_a_paper(self, client, scenario):
        paper, _, _ = _start(client, scenario)
        assert len(paper["questions"]) == 4
        assert paper["seconds_remaining"] > 0
        assert paper["exam_token"]

    def test_the_answer_key_never_reaches_the_candidate(self, client, scenario):
        paper, _, _ = _start(client, scenario)
        for question in paper["questions"]:
            for option in question["options"]:
                assert "is_correct" not in option

    def test_restarting_resumes_the_same_session(self, client, scenario):
        first, headers, _ = _start(client, scenario)
        second = client.post(f"/api/v1/exams/{scenario['exam'].id}/start", headers=headers).json()
        assert first["session_id"] == second["session_id"]
        assert [q["question_id"] for q in first["questions"]] == [
            q["question_id"] for q in second["questions"]
        ]

    def test_another_candidate_gets_a_different_paper(self, client, db, scenario):
        other = make_user(db, role=UserRole.CANDIDATE)
        enroll(db, scenario["exam"], other)
        mine, _, _ = _start(client, scenario)
        theirs = client.post(
            f"/api/v1/exams/{scenario['exam'].id}/start", headers=auth_headers(client, other)
        ).json()
        assert mine["session_id"] != theirs["session_id"]

    def test_examiner_cannot_sit_an_exam(self, client, scenario):
        response = client.post(
            f"/api/v1/exams/{scenario['exam'].id}/start",
            headers=auth_headers(client, scenario["examiner"]),
        )
        assert response.status_code == 403


class TestAnswering:
    def test_autosave_and_rehydrate(self, client, scenario):
        paper, headers, exam_headers = _start(client, scenario)
        question = next(q for q in paper["questions"] if q["question_type"] == "short_answer")

        save = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{question['question_id']}",
            headers=exam_headers,
            json={"text_answer": "Normalisation reduces redundancy."},
        )
        assert save.status_code == 200

        rehydrated = client.get(f"/api/v1/sessions/{paper['session_id']}", headers=headers).json()
        saved = next(
            q for q in rehydrated["questions"] if q["question_id"] == question["question_id"]
        )
        assert saved["saved_text"] == "Normalisation reduces redundancy."

    def test_saving_without_the_exam_token_is_rejected(self, client, scenario):
        paper, headers, _ = _start(client, scenario)
        question = paper["questions"][0]
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{question['question_id']}",
            headers=headers,
            json={"text_answer": "x"},
        )
        assert response.status_code == 401

    def test_another_candidates_exam_token_is_rejected(self, client, db, scenario):
        paper, _, exam_headers = _start(client, scenario)
        intruder = make_user(db, role=UserRole.CANDIDATE)
        stolen = {
            **auth_headers(client, intruder),
            "X-Exam-Token": exam_headers["X-Exam-Token"],
        }
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{paper['questions'][0]['question_id']}",
            headers=stolen,
            json={"text_answer": "let me in"},
        )
        assert response.status_code == 401

    def test_saving_a_question_not_on_the_paper_is_404(self, client, scenario):
        paper, _, exam_headers = _start(client, scenario)
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{uuid.uuid4()}",
            headers=exam_headers,
            json={"text_answer": "x"},
        )
        assert response.status_code == 404


class TestHeartbeat:
    def test_heartbeat_returns_server_time_and_a_fresh_token(self, client, scenario):
        paper, _, exam_headers = _start(client, scenario)
        response = client.post(
            f"/api/v1/sessions/{paper['session_id']}/heartbeat", headers=exam_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["seconds_remaining"] > 0
        assert body["status"] == "in_progress"
        assert body["exam_token"]


class TestProctoring:
    def test_events_raise_the_suspicion_score(self, client, scenario):
        from datetime import UTC, datetime

        paper, _, exam_headers = _start(client, scenario)
        now = datetime.now(UTC).isoformat()

        response = client.post(
            f"/api/v1/sessions/{paper['session_id']}/proctor/events",
            headers=exam_headers,
            json={
                "events": [
                    {"event_type": "tab_switch", "occurred_at": now},
                    {"event_type": "gaze_away", "occurred_at": now},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] == 2
        assert body["suspicion_score"] > 0
        assert body["tab_switch_count"] == 1

    def test_enough_events_flag_the_session(self, client, scenario):
        from datetime import UTC, datetime

        paper, _, exam_headers = _start(client, scenario)
        now = datetime.now(UTC).isoformat()

        body = client.post(
            f"/api/v1/sessions/{paper['session_id']}/proctor/events",
            headers=exam_headers,
            json={
                "events": [
                    {"event_type": "multiple_faces", "occurred_at": now},
                    {"event_type": "multiple_faces", "occurred_at": now},
                    {"event_type": "devtools_open", "occurred_at": now},
                    {"event_type": "camera_blocked", "occurred_at": now},
                ]
            },
        ).json()
        assert body["is_flagged"] is True

    def test_examiner_sees_the_timeline(self, client, scenario):
        from datetime import UTC, datetime

        paper, _, exam_headers = _start(client, scenario)
        client.post(
            f"/api/v1/sessions/{paper['session_id']}/proctor/events",
            headers=exam_headers,
            json={
                "events": [
                    {"event_type": "tab_switch", "occurred_at": datetime.now(UTC).isoformat()}
                ]
            },
        )
        review = client.get(
            f"/api/v1/proctoring/sessions/{paper['session_id']}",
            headers=auth_headers(client, scenario["examiner"]),
        )
        assert review.status_code == 200
        body = review.json()
        assert len(body["events"]) == 1
        assert body["events"][0]["event_type"] == "tab_switch"
        assert body["breakdown"]["tab_switch"] > 0

    def test_a_candidate_cannot_read_the_review_panel(self, client, scenario):
        paper, headers, _ = _start(client, scenario)
        response = client.get(f"/api/v1/proctoring/sessions/{paper['session_id']}", headers=headers)
        assert response.status_code == 403


class TestSubmitAndGrade:
    def test_full_flow_scores_objective_and_queues_subjective(self, client, db, scenario):
        paper, headers, exam_headers = _start(client, scenario)
        questions = scenario["questions"]

        for item in paper["questions"]:
            question = questions[uuid.UUID(item["question_id"])]
            url = f"/api/v1/sessions/{paper['session_id']}/answers/{item['question_id']}"

            if question.question_type in {QuestionType.MCQ, QuestionType.MULTI_SELECT}:
                correct = [str(o.id) for o in question.options if o.is_correct]
                client.put(url, headers=exam_headers, json={"selected_option_ids": correct})
            else:
                client.put(
                    url,
                    headers=exam_headers,
                    json={
                        "text_answer": (
                            "Normalisation organises tables to reduce redundancy and "
                            "improve integrity, avoiding update anomalies."
                        )
                    },
                )

        submit = client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)
        assert submit.status_code == 200, submit.text
        body = submit.json()
        assert body["status"] == SessionStatus.SUBMITTED.value
        assert body["auto_scored"] == 3  # 2 MCQ + 1 multi-select
        assert body["pending_review"] == 1  # the short answer

    def test_grading_queue_carries_the_provisional_score(self, client, db, scenario):
        from app.services.exam_engine import grade_pending_answers

        paper, _, exam_headers = _start(client, scenario)
        short = next(q for q in paper["questions"] if q["question_type"] == "short_answer")
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{short['question_id']}",
            headers=exam_headers,
            json={"text_answer": "Normalisation reduces redundancy and improves integrity."},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)

        # The API runs this as a background task; drive it directly so the test is not racy.
        graded = grade_pending_answers(db, uuid.UUID(paper["session_id"]))
        assert graded == 1

        queue = client.get(
            "/api/v1/grading/queue", headers=auth_headers(client, scenario["examiner"])
        )
        assert queue.status_code == 200
        items = queue.json()
        assert len(items) == 1
        assert items[0]["ai_evaluation"] is not None
        assert items[0]["grade_status"] == GradeStatus.AI_SCORED.value
        assert "Provisional offline score" in items[0]["ai_evaluation"]["justification"]

    def test_examiner_override_wins(self, client, db, scenario):
        from app.services.exam_engine import grade_pending_answers

        paper, _, exam_headers = _start(client, scenario)
        short = next(q for q in paper["questions"] if q["question_type"] == "short_answer")
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{short['question_id']}",
            headers=exam_headers,
            json={"text_answer": "A partial answer."},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)
        grade_pending_answers(db, uuid.UUID(paper["session_id"]))

        examiner_headers = auth_headers(client, scenario["examiner"])
        answer_id = client.get("/api/v1/grading/queue", headers=examiner_headers).json()[0][
            "answer_id"
        ]

        response = client.post(
            f"/api/v1/grading/answers/{answer_id}/score",
            headers=examiner_headers,
            json={"awarded_marks": 4.5, "comment": "Good, missed the anomaly point."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["awarded_marks"] == 4.5
        assert body["grade_status"] == GradeStatus.EXAMINER_REVIEWED.value

    def test_override_above_max_marks_rejected(self, client, db, scenario):
        from app.services.exam_engine import grade_pending_answers

        paper, _, exam_headers = _start(client, scenario)
        short = next(q for q in paper["questions"] if q["question_type"] == "short_answer")
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{short['question_id']}",
            headers=exam_headers,
            json={"text_answer": "An answer."},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)
        grade_pending_answers(db, uuid.UUID(paper["session_id"]))

        examiner_headers = auth_headers(client, scenario["examiner"])
        answer_id = client.get("/api/v1/grading/queue", headers=examiner_headers).json()[0][
            "answer_id"
        ]
        response = client.post(
            f"/api/v1/grading/answers/{answer_id}/score",
            headers=examiner_headers,
            json={"awarded_marks": 99},
        )
        assert response.status_code == 422

    def test_results_cannot_publish_while_review_is_outstanding(self, client, db, scenario):
        paper, _, exam_headers = _start(client, scenario)
        short = next(q for q in paper["questions"] if q["question_type"] == "short_answer")
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{short['question_id']}",
            headers=exam_headers,
            json={"text_answer": "An answer."},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)

        response = client.post(
            f"/api/v1/exams/{scenario['exam'].id}/results/publish",
            headers=auth_headers(client, scenario["examiner"]),
        )
        assert response.status_code == 409
        assert "examiner review" in response.json()["detail"]

    def test_publish_then_candidate_sees_the_result(self, client, db, scenario):
        from app.services.exam_engine import grade_pending_answers

        paper, headers, exam_headers = _start(client, scenario)
        questions = scenario["questions"]

        for item in paper["questions"]:
            question = questions[uuid.UUID(item["question_id"])]
            url = f"/api/v1/sessions/{paper['session_id']}/answers/{item['question_id']}"
            if question.question_type in {QuestionType.MCQ, QuestionType.MULTI_SELECT}:
                correct = [str(o.id) for o in question.options if o.is_correct]
                client.put(url, headers=exam_headers, json={"selected_option_ids": correct})
            else:
                client.put(url, headers=exam_headers, json={"text_answer": "A written answer."})

        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)
        grade_pending_answers(db, uuid.UUID(paper["session_id"]))

        examiner_headers = auth_headers(client, scenario["examiner"])
        answer_id = client.get("/api/v1/grading/queue", headers=examiner_headers).json()[0][
            "answer_id"
        ]
        client.post(
            f"/api/v1/grading/answers/{answer_id}/score",
            headers=examiner_headers,
            json={"awarded_marks": 3.0, "comment": "Partly right."},
        )

        publish = client.post(
            f"/api/v1/exams/{scenario['exam'].id}/results/publish", headers=examiner_headers
        )
        assert publish.status_code == 200, publish.text

        results = client.get("/api/v1/my/results", headers=headers).json()
        assert len(results) == 1
        # 2 MCQ x 2 + 1 multi-select x 4 + 3 examiner marks = 11
        assert results[0]["obtained_marks"] == 11.0
        assert results[0]["published"] is True

        detail = client.get(f"/api/v1/results/{results[0]['id']}", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["questions"]) == 4

    def test_a_candidate_cannot_read_another_candidates_result(self, client, db, scenario):
        from app.services.exam_engine import grade_pending_answers

        paper, _, exam_headers = _start(client, scenario)
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)
        grade_pending_answers(db, uuid.UUID(paper["session_id"]))

        examiner_headers = auth_headers(client, scenario["examiner"])
        client.post(
            f"/api/v1/exams/{scenario['exam'].id}/results/publish", headers=examiner_headers
        )

        result_id = client.get(
            f"/api/v1/exams/{scenario['exam'].id}/results", headers=examiner_headers
        ).json()[0]["result_id"]

        intruder = make_user(db, role=UserRole.CANDIDATE)
        response = client.get(
            f"/api/v1/results/{result_id}", headers=auth_headers(client, intruder)
        )
        assert response.status_code == 403

    def test_submitting_twice_is_rejected(self, client, scenario):
        paper, _, exam_headers = _start(client, scenario)
        assert (
            client.post(
                f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers
            ).status_code
            == 409
        )
