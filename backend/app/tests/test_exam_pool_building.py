"""Building an exam's question pool from all four sources.

The pool is not the paper. These tests cover what an examiner assembles - order,
provenance, ownership, and what belongs in the reusable bank versus one exam only -
and stop short of what any single candidate is then shown.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Difficulty,
    Exam,
    ExamQuestion,
    ExamStatus,
    Question,
    QuestionCategory,
    QuestionSource,
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


def _pool_ids(client: TestClient, exam_id, headers) -> list[str]:
    response = client.get(f"/api/v1/exams/{exam_id}/pool", headers=headers)
    assert response.status_code == 200, response.text
    return [e["question_id"] for e in response.json()["entries"]]


class TestPoolOrdering:
    """order_index used to be read off the SELECT's row order, not the payload's."""

    def test_pool_keeps_the_order_the_examiner_sent(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(6)]
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        # Deliberately not the creation order, and not any sort of the ids.
        wanted = [str(questions[i].id) for i in (3, 0, 5, 1, 4, 2)]
        response = client.patch(
            f"/api/v1/exams/{exam.id}", json={"question_ids": wanted}, headers=headers
        )
        assert response.status_code == 200, response.text

        assert _pool_ids(client, exam.id, headers) == wanted

    def test_reorder_endpoint_rewrites_the_order(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(4)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        reversed_ids = [str(q.id) for q in reversed(questions)]
        response = client.put(
            f"/api/v1/exams/{exam.id}/questions/order",
            json={"question_ids": reversed_ids},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert [e["question_id"] for e in response.json()["entries"]] == reversed_ids

    def test_partial_order_is_refused_rather_than_guessed(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(4)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.put(
            f"/api/v1/exams/{exam.id}/questions/order",
            json={"question_ids": [str(q.id) for q in questions[:3]]},
            headers=headers,
        )
        assert response.status_code == 422
        assert "every question in the pool" in response.json()["detail"]

    def test_removing_a_question_closes_the_gap(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(4)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.delete(
            f"/api/v1/exams/{exam.id}/questions/{questions[1].id}", headers=headers
        )
        assert response.status_code == 200, response.text
        assert [e["order_index"] for e in response.json()["entries"]] == [0, 1, 2]


class TestPoolAppend:
    def test_adding_keeps_what_is_already_there(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        first = [make_question(db, subject) for _ in range(2)]
        extra = [make_question(db, subject) for _ in range(3)]
        exam = make_exam(db, subject, examiner, questions=first, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.post(
            f"/api/v1/exams/{exam.id}/questions",
            json={"question_ids": [str(q.id) for q in extra]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert _pool_ids(client, exam.id, headers) == [str(q.id) for q in first + extra]

    def test_adding_the_same_question_twice_is_a_no_op(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(2)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.post(
            f"/api/v1/exams/{exam.id}/questions",
            json={"question_ids": [str(questions[0].id)]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stats"]["total_questions"] == 2

    def test_pool_cannot_change_once_a_candidate_has_sat_it(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(2)]
        exam = make_exam(db, subject, examiner, questions=questions, candidates=[candidate])
        headers = auth_headers(client, examiner)

        started = client.post(
            f"/api/v1/exams/{exam.id}/start", headers=auth_headers(client, candidate)
        )
        assert started.status_code in (200, 201), started.text

        spare = make_question(db, subject)
        response = client.post(
            f"/api/v1/exams/{exam.id}/questions",
            json={"question_ids": [str(spare.id)]},
            headers=headers,
        )
        assert response.status_code == 409
        assert "already started" in response.json()["detail"]


class TestPoolStats:
    def test_distribution_counts_types_and_difficulties(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [
            make_question(db, subject, difficulty=Difficulty.EASY, marks=1),
            make_question(db, subject, difficulty=Difficulty.EASY, marks=1),
            make_question(db, subject, difficulty=Difficulty.HARD, marks=5),
            make_question(
                db,
                subject,
                qtype=QuestionType.LONG_ANSWER,
                difficulty=Difficulty.HARD,
                marks=10,
                option_count=0,
            ),
        ]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        stats = client.get(f"/api/v1/exams/{exam.id}/pool", headers=headers).json()["stats"]
        assert stats["total_questions"] == 4
        assert stats["total_marks"] == 17.0
        assert stats["by_type"] == {"mcq": 3, "long_answer": 1}
        assert stats["by_difficulty"] == {"easy": 2, "hard": 2}

    def test_marks_override_reweights_this_exam_only(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, marks=2)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.patch(
            f"/api/v1/exams/{exam.id}/questions/{question.id}/marks",
            json={"marks_override": 7},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["stats"]["total_marks"] == 7.0
        # The bank copy is untouched - the override is per-exam by design.
        db.refresh(question)
        assert question.marks == 2


class TestAuthoringIntoAnExam:
    def _mcq_payload(self, subject_id, **extra) -> dict:
        return {
            "subject_id": str(subject_id),
            "question_type": "mcq",
            "difficulty": "medium",
            "body": "What is supervised learning?",
            "marks": 2,
            "negative_marks": 0.5,
            "options": [
                {"text": "Learning without data", "is_correct": False, "order_index": 0},
                {"text": "Learning from labelled data", "is_correct": True, "order_index": 1},
                {"text": "Removing training data", "is_correct": False, "order_index": 2},
                {"text": "Encrypting data", "is_correct": False, "order_index": 3},
            ],
            **extra,
        }

    def test_saving_with_an_exam_id_lands_in_that_pool(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(subject.id, exam_id=str(exam.id)),
            headers=headers,
        )
        assert response.status_code == 201, response.text
        created = response.json()
        assert created["exam_only"] is False  # save_to_bank defaults to true
        assert _pool_ids(client, exam.id, headers) == [created["id"]]

    def test_declining_the_bank_keeps_the_question_out_of_the_browser(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        created = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(subject.id, exam_id=str(exam.id), save_to_bank=False),
            headers=headers,
        ).json()
        assert created["exam_only"] is True

        listed = client.get(f"/api/v1/questions?subject_id={subject.id}", headers=headers).json()
        assert created["id"] not in [q["id"] for q in listed]

        # ...but it is visible when the exam that owns it is named.
        scoped = client.get(
            f"/api/v1/questions?subject_id={subject.id}&exam_id={exam.id}", headers=headers
        ).json()
        assert [q["id"] for q in scoped] == [created["id"]]

    def test_an_exam_only_question_cannot_be_borrowed_by_another_exam(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        owner_exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        other_exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        private = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(subject.id, exam_id=str(owner_exam.id), save_to_bank=False),
            headers=headers,
        ).json()

        response = client.post(
            f"/api/v1/exams/{other_exam.id}/questions",
            json={"question_ids": [private["id"]]},
            headers=headers,
        )
        assert response.status_code == 422
        assert "privately to another exam" in response.json()["detail"]

    def test_authoring_into_another_examiners_exam_is_refused(
        self, client: TestClient, db: Session
    ):
        owner = make_user(db, role=UserRole.EXAMINER)
        intruder = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, owner, questions=[], status=ExamStatus.DRAFT)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(subject.id, exam_id=str(exam.id)),
            headers=auth_headers(client, intruder),
        )
        assert response.status_code == 403

    def test_subject_must_match_the_exam(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        elsewhere = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(elsewhere.id, exam_id=str(exam.id)),
            headers=auth_headers(client, examiner),
        )
        assert response.status_code == 422


class TestProvenanceAndOwnership:
    def test_source_defaults_to_manual_and_is_filterable(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        make_question(db, subject, created_by=examiner)
        imported = make_question(db, subject, created_by=examiner)
        imported.source = QuestionSource.IMPORTED
        db.flush()
        headers = auth_headers(client, examiner)

        listed = client.get(
            f"/api/v1/questions?subject_id={subject.id}&source=imported", headers=headers
        ).json()
        assert [q["id"] for q in listed] == [str(imported.id)]

    def test_mine_filters_to_the_callers_own_questions(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        other = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        ours = make_question(db, subject, created_by=examiner)
        make_question(db, subject, created_by=other)

        listed = client.get(
            f"/api/v1/questions?subject_id={subject.id}&mine=true",
            headers=auth_headers(client, examiner),
        ).json()
        assert [q["id"] for q in listed] == [str(ours.id)]

    def test_another_examiners_question_cannot_be_edited(self, client: TestClient, db: Session):
        owner = make_user(db, role=UserRole.EXAMINER)
        intruder = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, created_by=owner)

        response = client.patch(
            f"/api/v1/questions/{question.id}",
            json={"body": "Rewritten by someone else"},
            headers=auth_headers(client, intruder),
        )
        assert response.status_code == 403
        assert "Duplicate it" in response.json()["detail"]

    def test_an_admin_may_edit_anyones_question(self, client: TestClient, db: Session):
        owner = make_user(db, role=UserRole.EXAMINER)
        admin = make_user(db, role=UserRole.ADMIN)
        subject = make_subject(db)
        question = make_question(db, subject, created_by=owner)

        response = client.patch(
            f"/api/v1/questions/{question.id}",
            json={"difficulty": "hard"},
            headers=auth_headers(client, admin),
        )
        assert response.status_code == 200, response.text

    def test_duplicating_copies_the_answer_key_into_the_callers_name(
        self, client: TestClient, db: Session
    ):
        owner = make_user(db, role=UserRole.EXAMINER)
        borrower = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        original = make_question(db, subject, created_by=owner, correct_indices=[2])

        response = client.post(
            f"/api/v1/questions/{original.id}/duplicate",
            json={},
            headers=auth_headers(client, borrower),
        )
        assert response.status_code == 201, response.text
        copy = response.json()
        assert copy["id"] != str(original.id)
        assert copy["created_by_id"] == str(borrower.id)
        assert [o["is_correct"] for o in copy["options"]] == [False, False, True, False]

        # The original is untouched.
        db.refresh(original)
        assert original.created_by_id == owner.id

    def test_duplicating_into_an_exam_adds_the_copy_to_that_pool(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        original = make_question(db, subject, created_by=examiner)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        copy = client.post(
            f"/api/v1/questions/{original.id}/duplicate",
            json={"exam_id": str(exam.id)},
            headers=headers,
        ).json()
        assert _pool_ids(client, exam.id, headers) == [copy["id"]]


class TestSelectionRuleNarrowing:
    """Category and topic on a rule were parsed and then dropped before this."""

    def test_a_category_rule_only_draws_from_that_category(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        aptitude = [
            make_question(db, subject, category=QuestionCategory.APTITUDE) for _ in range(3)
        ]
        technical = [
            make_question(db, subject, category=QuestionCategory.TECHNICAL) for _ in range(3)
        ]
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=aptitude + technical,
            status=ExamStatus.DRAFT,
            rules=[
                {
                    "question_type": "mcq",
                    "difficulty": "easy",
                    "count": 3,
                    "category": "aptitude",
                }
            ],
        )
        headers = auth_headers(client, examiner)

        check = client.get(f"/api/v1/exams/{exam.id}/pool-check", headers=headers).json()
        assert check["can_publish"] is True

        candidate = make_user(db, role=UserRole.CANDIDATE)
        preview = client.post(
            f"/api/v1/exams/{exam.id}/preview-paper",
            json={"candidate_id": str(candidate.id)},
            headers=headers,
        )
        assert preview.status_code == 200, preview.text
        drawn = {uuid.UUID(e["question_id"]) for e in preview.json()["entries"]}
        assert drawn <= {q.id for q in aptitude}

    def test_a_rule_with_too_few_matching_questions_blocks_publishing(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [
            make_question(db, subject, category=QuestionCategory.TECHNICAL) for _ in range(5)
        ]
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=questions,
            status=ExamStatus.DRAFT,
            rules=[
                {
                    "question_type": "mcq",
                    "difficulty": "easy",
                    "count": 2,
                    "category": "aptitude",
                }
            ],
        )
        headers = auth_headers(client, examiner)

        check = client.get(f"/api/v1/exams/{exam.id}/pool-check", headers=headers).json()
        assert check["can_publish"] is False
        assert "in aptitude" in check["problems"][0]

    def test_a_topic_rule_matches_case_insensitively(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        on_topic = [make_question(db, subject, topic="Percentages") for _ in range(2)]
        make_question(db, subject, topic="Blood Relations")
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=on_topic,
            status=ExamStatus.DRAFT,
            rules=[
                {
                    "question_type": "mcq",
                    "difficulty": "easy",
                    "count": 2,
                    "topic": "percentages",
                }
            ],
        )
        check = client.get(
            f"/api/v1/exams/{exam.id}/pool-check", headers=auth_headers(client, examiner)
        ).json()
        assert check["can_publish"] is True


def test_deleting_an_exam_takes_its_private_questions_with_it(client: TestClient, db: Session):
    """origin_exam_id cascades.

    A question that exists only for one exam has no meaning once that exam is gone,
    and leaving it behind would litter the bank with orphans nobody can find.
    """
    examiner = make_user(db, role=UserRole.EXAMINER)
    subject = make_subject(db)
    exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
    headers = auth_headers(client, examiner)

    private = client.post(
        "/api/v1/questions",
        json={
            "subject_id": str(subject.id),
            "question_type": "true_false",
            "body": "Gradient descent minimises a loss function.",
            "marks": 1,
            "exam_id": str(exam.id),
            "save_to_bank": False,
            "options": [
                {"text": "True", "is_correct": True, "order_index": 0},
                {"text": "False", "is_correct": False, "order_index": 1},
            ],
        },
        headers=headers,
    ).json()

    assert client.delete(f"/api/v1/exams/{exam.id}", headers=headers).status_code == 200
    db.expire_all()
    assert db.get(Question, uuid.UUID(private["id"])) is None
    assert db.scalar(select(Exam).where(Exam.id == exam.id)) is None
    assert db.scalar(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)) is None
