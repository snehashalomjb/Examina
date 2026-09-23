"""The exam blueprint: fill the pool from bank-wide criteria in one call.

"Python MCQ Medium 10" should turn into a section plus every matching bank question
added to the pool, unpinned so the section's rule can randomly draw from them - without
an examiner first hand-searching the bank and adding matches one at a time.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Difficulty, ExamStatus, QuestionType, UserRole
from app.tests.conftest import auth_headers, make_exam, make_question, make_subject, make_user

API = "/api/v1"


def _blueprint(client, headers, exam_id, rows) -> dict:
    response = client.post(f"{API}/exams/{exam_id}/blueprint", json={"rows": rows}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestBlueprint:
    def test_matching_questions_are_pulled_into_the_pool_unpinned(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        for _ in range(5):
            make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.MEDIUM)
        # A distractor the row must not pick up.
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.HARD)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        result = _blueprint(
            client,
            headers,
            exam.id,
            [
                {
                    "title": "Python",
                    "subject_id": str(subject.id),
                    "question_type": "mcq",
                    "difficulty": "medium",
                    "count": 3,
                }
            ],
        )

        row = result["rows"][0]
        assert row["title"] == "Python"
        assert row["matched"] == 5
        assert row["added"] == 5
        assert result["pool"]["stats"]["total_questions"] == 5

        pool = client.get(f"{API}/exams/{exam.id}/pool", headers=headers).json()
        assert all(e["section_id"] is None for e in pool["entries"])

        sections = client.get(f"{API}/exams/{exam.id}", headers=headers).json()["sections"]
        assert len(sections) == 1
        assert sections[0]["selection_rules"]["rules"][0]["count"] == 3

    def test_shortfall_is_reported_not_hidden(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.HARD)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        result = _blueprint(
            client,
            headers,
            exam.id,
            [
                {
                    "title": "Thin Section",
                    "subject_id": str(subject.id),
                    "question_type": "mcq",
                    "difficulty": "hard",
                    "count": 10,
                }
            ],
        )

        row = result["rows"][0]
        assert row["requested"] == 10
        assert row["matched"] == 1
        assert row["added"] == 1
        assert result["pool"]["can_publish"] is False

    def test_multiple_rows_each_become_their_own_section(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        for _ in range(2):
            make_question(db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY)
        for _ in range(2):
            make_question(db, subject, qtype=QuestionType.TRUE_FALSE, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        result = _blueprint(
            client,
            headers,
            exam.id,
            [
                {
                    "title": "MCQ Round",
                    "subject_id": str(subject.id),
                    "question_type": "mcq",
                    "count": 2,
                },
                {
                    "title": "True/False Round",
                    "subject_id": str(subject.id),
                    "question_type": "true_false",
                    "count": 2,
                },
            ],
        )

        assert [r["title"] for r in result["rows"]] == ["MCQ Round", "True/False Round"]
        assert result["pool"]["stats"]["total_questions"] == 4

    def test_tag_narrowing_only_pulls_tagged_questions(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        tagged = make_question(db, subject, qtype=QuestionType.MCQ)
        tagged.tags = ["Python", "OOP"]
        make_question(db, subject, qtype=QuestionType.MCQ)  # untagged distractor
        db.flush()
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        result = _blueprint(
            client,
            headers,
            exam.id,
            [
                {
                    "title": "OOP",
                    "subject_id": str(subject.id),
                    "question_type": "mcq",
                    "tags": ["OOP"],
                    "count": 5,
                }
            ],
        )

        assert result["rows"][0]["matched"] == 1
        pool = client.get(f"{API}/exams/{exam.id}/pool", headers=headers).json()
        assert [e["question_id"] for e in pool["entries"]] == [str(tagged.id)]

    def test_repeated_title_gets_a_suffix_instead_of_colliding(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        make_question(db, subject, qtype=QuestionType.MCQ)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        row = {
            "title": "Python",
            "subject_id": str(subject.id),
            "question_type": "mcq",
            "count": 1,
        }
        _blueprint(client, headers, exam.id, [row])
        result = _blueprint(client, headers, exam.id, [row])

        assert result["rows"][0]["title"] == "Python (2)"
        assert result["rows"][0]["added"] == 0  # the only match was already pooled

    def test_cannot_change_a_published_exam_with_sessions(self, client: TestClient, db: Session):
        from app.tests.conftest import enroll

        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.MCQ)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)
        enroll(db, exam, candidate)
        headers = auth_headers(client, examiner)
        candidate_headers = auth_headers(client, candidate)
        start = client.post(f"{API}/exams/{exam.id}/start", headers=candidate_headers)
        assert start.status_code == 200, start.text

        response = client.post(
            f"{API}/exams/{exam.id}/blueprint",
            json={
                "rows": [
                    {
                        "title": "Python",
                        "subject_id": str(subject.id),
                        "question_type": "mcq",
                        "count": 1,
                    }
                ]
            },
            headers=headers,
        )
        assert response.status_code == 409
