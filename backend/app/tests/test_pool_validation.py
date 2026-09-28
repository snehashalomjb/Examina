"""Publish-time pool validation: questions chosen for a section count towards its rule.

The bug these pin down: an examiner chose 10 DBMS questions for "General Section", the
picker showed "10 chosen of 10", and publishing was still refused with "pool only has 0
left". The exam builder saved the rule's subject *name* in ``topic``, the validator
compared that with each question's own topic ("Normalization", "Joins", ...), and so
none of the chosen questions matched. What counts is the chosen questions that satisfy
the rule plus the shared ones that do - and nothing more once the rule is met.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Difficulty,
    Exam,
    ExamSection,
    ExamStatus,
    ExamType,
    QuestionCategory,
    QuestionType,
    UserRole,
)
from app.services.paper_generator import check_pool_satisfies_rules
from app.tests.conftest import auth_headers, make_exam, make_question, make_subject, make_user

API = "/api/v1"


def _rule(**overrides) -> dict:
    rule = {
        "question_type": "mcq",
        "difficulty": "medium",
        "category": "academic",
        "topic": "DBMS",  # the subject's name, exactly as the exam builder saved it
        "count": 10,
    }
    rule.update(overrides)
    return {"rules": [rule]}


def _dbms_exam(db: Session, *, pinned: int, shared: int, rules: dict | None = None):
    """An academic DBMS exam with ``pinned`` questions chosen for its one section and
    ``shared`` more left in the shared pool. Every question matches the default rule."""
    examiner = make_user(db, role=UserRole.EXAMINER)
    subject = make_subject(db)
    subject.name = "DBMS"
    questions = [
        make_question(
            db,
            subject,
            difficulty=Difficulty.MEDIUM,
            topic=["Normalization", "Joins", "Transactions"][i % 3],
            created_by=examiner,
        )
        for i in range(pinned + shared)
    ]
    exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)
    section = ExamSection(
        exam_id=exam.id, name="General Section", order_index=0, selection_rules=rules or _rule()
    )
    db.add(section)
    db.flush()
    for entry in exam.exam_questions[:pinned]:
        entry.section_id = section.id
    db.flush()
    db.refresh(exam)
    return exam, section, questions, examiner, subject


class TestCountingChosenAndSharedQuestions:
    def test_ten_required_ten_chosen_none_shared_passes(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0)
        assert check_pool_satisfies_rules(exam) == []

    def test_ten_required_five_chosen_five_shared_passes(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=5, shared=5)
        assert check_pool_satisfies_rules(exam) == []

    def test_ten_required_five_chosen_none_shared_fails_with_the_real_count(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=5, shared=0)
        problems = check_pool_satisfies_rules(exam)
        assert len(problems) == 1
        assert "Need 10" in problems[0] and "has 5 left" in problems[0]

    def test_a_met_rule_needs_nothing_more_from_the_shared_pool(self, db: Session):
        """Ten chosen and thirty shared: the shared ones are simply not needed."""
        exam, *_ = _dbms_exam(db, pinned=10, shared=30)
        assert check_pool_satisfies_rules(exam) == []


class TestRuleMatching:
    def test_rule_values_are_matched_whatever_their_spelling_or_case(self, db: Session):
        rules = _rule(question_type="SINGLE_CHOICE", difficulty="MEDIUM", category="Academic",
                      topic="dbms")
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=rules)
        assert check_pool_satisfies_rules(exam) == []

    def test_mcq_upper_case_is_single_choice(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(question_type="MCQ"))
        assert check_pool_satisfies_rules(exam) == []

    def test_any_subject_does_not_narrow_to_a_subject(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(topic="Any subject"))
        assert check_pool_satisfies_rules(exam) == []

    def test_a_rule_naming_the_subject_by_id_passes(self, db: Session):
        exam, _, _, _, subject = _dbms_exam(db, pinned=10, shared=0)
        exam.sections[0].selection_rules = _rule(topic=None, subject_id=str(subject.id).upper())
        db.flush()
        assert check_pool_satisfies_rules(exam) == []

    def test_subject_mismatch_is_rejected(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0)
        other = make_subject(db)
        exam.sections[0].selection_rules = _rule(topic=None, subject_id=str(other.id))
        db.flush()
        assert "has 0 left" in check_pool_satisfies_rules(exam)[0]

    def test_subject_named_in_topic_must_be_the_questions_subject(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(topic="Operating Systems"))
        assert "has 0 left" in check_pool_satisfies_rules(exam)[0]

    def test_difficulty_mismatch_is_rejected(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(difficulty="hard"))
        assert "has 0 left" in check_pool_satisfies_rules(exam)[0]

    def test_type_mismatch_is_rejected(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(question_type="multi_select"))
        assert "has 0 left" in check_pool_satisfies_rules(exam)[0]

    def test_category_mismatch_is_rejected(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(category="technical"))
        assert "has 0 left" in check_pool_satisfies_rules(exam)[0]

    def test_a_real_topic_still_narrows(self, db: Session):
        exam, *_ = _dbms_exam(db, pinned=10, shared=0, rules=_rule(topic="Joins", count=3))
        assert check_pool_satisfies_rules(exam) == []
        exam.sections[0].selection_rules = _rule(topic="Joins", count=4)
        db.flush()
        assert "has 3 left" in check_pool_satisfies_rules(exam)[0]


class TestNoDuplicatesInThePool:
    def _add(self, client: TestClient, examiner, exam: Exam, ids, section_id=None):
        return client.post(
            f"{API}/exams/{exam.id}/questions",
            headers=auth_headers(client, examiner),
            json={
                "question_ids": [str(i) for i in ids],
                "section_id": str(section_id) if section_id else None,
            },
        )

    def test_the_same_question_id_twice_is_rejected(self, client: TestClient, db: Session):
        exam, section, _, examiner, subject = _dbms_exam(db, pinned=0, shared=0)
        q = make_question(db, subject, difficulty=Difficulty.MEDIUM, created_by=examiner)
        response = self._add(client, examiner, exam, [q.id, q.id], section.id)
        assert response.status_code == 422, response.text
        assert "more than once" in response.json()["detail"]

    def test_a_same_text_copy_under_a_new_id_is_rejected(self, client: TestClient, db: Session):
        exam, section, questions, examiner, subject = _dbms_exam(db, pinned=1, shared=0)
        copy = make_question(
            db, subject, difficulty=Difficulty.MEDIUM, body=f"  {questions[0].body.upper()} ",
            created_by=examiner,
        )
        response = self._add(client, examiner, exam, [copy.id], section.id)
        assert response.status_code == 409, response.text
        assert "same text" in response.json()["detail"]

    def test_a_shared_question_chosen_for_a_section_becomes_pinned(
        self, client: TestClient, db: Session
    ):
        """It used to be ignored as "already present" - counted by the picker, never by
        the validator."""
        exam, section, questions, examiner, _ = _dbms_exam(db, pinned=0, shared=1)
        response = self._add(client, examiner, exam, [questions[0].id], section.id)
        assert response.status_code == 200, response.text
        entry = next(e for e in response.json()["entries"] if e["question_id"] == str(questions[0].id))
        assert entry["section_id"] == str(section.id)

    def test_a_question_chosen_for_another_section_is_rejected(
        self, client: TestClient, db: Session
    ):
        exam, _, questions, examiner, _ = _dbms_exam(db, pinned=1, shared=0)
        other = ExamSection(exam_id=exam.id, name="Other", order_index=1, selection_rules=_rule())
        db.add(other)
        db.flush()
        response = self._add(client, examiner, exam, [questions[0].id], other.id)
        assert response.status_code == 409, response.text

    def test_question_type_and_category_enums_are_what_the_fixture_built(self, db: Session):
        """Guard for the fixtures above: every question really is academic medium MCQ."""
        exam, *_ = _dbms_exam(db, pinned=2, shared=0)
        for entry in exam.exam_questions:
            assert entry.question.question_type is QuestionType.MCQ
            assert entry.question.category is QuestionCategory.ACADEMIC


class TestExplainingTheShortfall:
    def test_chosen_questions_that_fail_the_rule_are_explained(self, db: Session):
        """The real case: ten chosen questions filed as technical, rule asks academic."""
        exam, *_ = _dbms_exam(db, pinned=10, shared=0)  # rule asks for academic
        for entry in exam.exam_questions:
            entry.question.category = QuestionCategory.TECHNICAL
        db.flush()
        problem = check_pool_satisfies_rules(exam)[0]
        assert "has 0 left" in problem
        assert "10 question(s) chosen for this section do not fit its rule" in problem
        assert "filed as technical, the rule asks for academic" in problem


class TestChoosingForASectionMustFitItsRules:
    def test_a_question_from_another_subject_is_refused_with_the_reason(
        self, client: TestClient, db: Session
    ):
        """The reported bug: Python questions chosen for a SQL section were accepted, and
        publishing then said the SQL rule had nothing to draw."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        python, sql = make_subject(db), make_subject(db)
        python.name, sql.name = "Python", "SQL"
        py_questions = [
            make_question(db, python, difficulty=Difficulty.MEDIUM, created_by=examiner)
            for _ in range(2)
        ]
        exam = make_exam(db, python, examiner, questions=[], status=ExamStatus.DRAFT)
        exam.exam_type = ExamType.CORPORATE  # a multi-subject paper
        section = ExamSection(
            exam_id=exam.id, name="SQL", order_index=0,
            selection_rules=_rule(topic=None, category=None, subject_id=str(sql.id), count=2),
        )
        db.add(section)
        db.flush()

        response = client.post(
            f"{API}/exams/{exam.id}/questions",
            headers=auth_headers(client, examiner),
            json={"question_ids": [str(q.id) for q in py_questions], "section_id": str(section.id)},
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert "do not fit SQL's rules" in detail and "Python question" in detail

    def test_a_fitting_question_is_accepted(self, client: TestClient, db: Session):
        exam, section, _, examiner, subject = _dbms_exam(db, pinned=0, shared=0)
        q = make_question(db, subject, difficulty=Difficulty.MEDIUM, created_by=examiner)
        response = client.post(
            f"{API}/exams/{exam.id}/questions",
            headers=auth_headers(client, examiner),
            json={"question_ids": [str(q.id)], "section_id": str(section.id)},
        )
        assert response.status_code == 200, response.text
