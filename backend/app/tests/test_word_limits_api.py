"""Word limits end to end: configuring them, sitting under them, grading against them."""

from __future__ import annotations

import pytest

from app.db.models import AccessStatus, Difficulty, QuestionType, UserRole
from app.tests.conftest import (
    auth_headers,
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

    essay = make_question(
        db,
        subject,
        qtype=QuestionType.LONG_ANSWER,
        difficulty=Difficulty.MEDIUM,
        marks=10.0,
        negative=0.0,
        min_words=10,
        max_words=20,
        body="Discuss normalisation in at most twenty words.",
    )
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=[essay],
        candidates=[candidate],
        rules=[{"question_type": "long_answer", "difficulty": None, "count": 1}],
    )
    return {"subject": subject, "examiner": examiner, "candidate": candidate, "exam": exam}


def _start(client, scenario):
    headers = auth_headers(client, scenario["candidate"])
    response = client.post(f"/api/v1/exams/{scenario['exam'].id}/start", headers=headers)
    assert response.status_code == 200, response.text
    paper = response.json()
    return paper, {**headers, "X-Exam-Token": paper["exam_token"]}


class TestConfiguringLimits:
    def test_an_examiner_can_set_word_bounds_on_a_long_answer(self, client, db, scenario):
        headers = auth_headers(client, scenario["examiner"])
        response = client.post(
            "/api/v1/questions",
            headers=headers,
            json={
                "subject_id": str(scenario["subject"].id),
                "question_type": "long_answer",
                "difficulty": "medium",
                "body": "Explain the CAP theorem.",
                "model_answer": "Consistency, availability, partition tolerance.",
                "marks": 10,
                "min_words": 150,
                "max_words": 400,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["min_words"] == 150
        assert response.json()["max_words"] == 400

    def test_a_minimum_above_the_maximum_is_rejected(self, client, db, scenario):
        headers = auth_headers(client, scenario["examiner"])
        response = client.post(
            "/api/v1/questions",
            headers=headers,
            json={
                "subject_id": str(scenario["subject"].id),
                "question_type": "long_answer",
                "body": "Explain the CAP theorem.",
                "model_answer": "Consistency, availability, partition tolerance.",
                "marks": 10,
                "min_words": 400,
                "max_words": 150,
            },
        )
        assert response.status_code == 422
        assert "min_words cannot exceed max_words" in response.text

    def test_word_bounds_on_an_mcq_are_rejected(self, client, db, scenario):
        headers = auth_headers(client, scenario["examiner"])
        response = client.post(
            "/api/v1/questions",
            headers=headers,
            json={
                "subject_id": str(scenario["subject"].id),
                "question_type": "mcq",
                "body": "Which one?",
                "marks": 2,
                "max_words": 50,
                "options": [
                    {"text": "Right", "is_correct": True, "order_index": 0},
                    {"text": "Wrong", "is_correct": False, "order_index": 1},
                ],
            },
        )
        assert response.status_code == 422
        assert "do not take a word limit" in response.text


class TestSittingWithinLimits:
    def test_the_paper_carries_the_bounds_to_the_runner(self, client, scenario):
        paper, _ = _start(client, scenario)
        question = paper["questions"][0]
        assert question["min_words"] == 10
        assert question["max_words"] == 20

    def test_an_answer_within_the_limit_saves_and_reports_its_count(self, client, scenario):
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={
                "text_answer": (
                    "Normalisation removes redundancy and protects integrity "
                    "across related tables in a schema."
                )
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["word_count"] == 12

    def test_an_answer_over_the_limit_is_refused(self, client, scenario):
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={"text_answer": " ".join(["word"] * 21)},
        )
        assert response.status_code == 422
        assert "limit for this question is 20" in response.text

    def test_a_half_typed_answer_below_the_minimum_still_saves(self, client, scenario):
        # Autosave must never throw away work just because the answer is not finished.
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        response = client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={"text_answer": "I would begin"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["word_count"] == 3

    def test_the_saved_count_comes_back_on_reload(self, client, scenario):
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={"text_answer": "one two three four five"},
        )
        reloaded = client.get(
            f"/api/v1/sessions/{paper['session_id']}", headers=exam_headers
        ).json()
        assert reloaded["questions"][0]["saved_word_count"] == 5


class TestGradingSeesTheShortfall:
    def test_an_under_length_answer_is_flagged_to_the_examiner(self, client, scenario):
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={"text_answer": "Too short."},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)

        queue = client.get(
            "/api/v1/grading/queue", headers=auth_headers(client, scenario["examiner"])
        ).json()
        item = next(i for i in queue if i["question_id"] == qid)
        assert item["word_count"] == 2
        assert item["words_below_minimum"] == 8

    def test_a_long_enough_answer_reports_no_shortfall(self, client, scenario):
        paper, exam_headers = _start(client, scenario)
        qid = paper["questions"][0]["question_id"]
        client.put(
            f"/api/v1/sessions/{paper['session_id']}/answers/{qid}",
            headers=exam_headers,
            json={"text_answer": " ".join(["word"] * 15)},
        )
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=exam_headers)

        queue = client.get(
            "/api/v1/grading/queue", headers=auth_headers(client, scenario["examiner"])
        ).json()
        item = next(i for i in queue if i["question_id"] == qid)
        assert item["words_below_minimum"] == 0
