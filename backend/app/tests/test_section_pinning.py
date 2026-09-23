"""Choosing questions *for* a section, rather than for the exam as a whole.

Sections used to be labels. Their rules were flattened into one list, the generator drew
from one undifferentiated pool, and "Section A" was a heading on the wizard that nothing
downstream could see. These tests cover the seam that makes a section real: a question
pinned to one is drawn for that section, is invisible to every other section, survives
the wizard's autosaves, and falls back to the shared pool if the section goes away.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Difficulty,
    Exam,
    ExamQuestion,
    ExamSection,
    ExamStatus,
    QuestionType,
    UserRole,
)
from app.services.paper_generator import check_pool_satisfies_rules, generate_paper
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)

RULES_ONE_EASY_MCQ = {"rules": [{"question_type": "mcq", "difficulty": "easy", "count": 1}]}


def _section(db: Session, exam: Exam, name: str, order: int, rules: dict) -> ExamSection:
    section = ExamSection(
        exam_id=exam.id, name=name, order_index=order, selection_rules=rules
    )
    db.add(section)
    db.flush()
    return section


def _pin(db: Session, exam: Exam, question, section: ExamSection | None) -> None:
    entry = next(eq for eq in exam.exam_questions if eq.question_id == question.id)
    entry.section_id = section.id if section else None
    db.flush()


class TestDrawingBySection:
    def test_a_pinned_question_is_always_the_one_its_section_gets(
        self, client: TestClient, db: Session
    ):
        """The point of choosing a question is that choosing it settles the matter."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        # Ten interchangeable questions; a random draw would almost never pick ours.
        questions = [make_question(db, subject, difficulty=Difficulty.EASY) for _ in range(10)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)

        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        _pin(db, exam, questions[7], section)
        db.refresh(exam)

        _, entries = generate_paper(exam=exam, candidate_id=candidate.id)

        assert [e.question_id for e in entries] == [questions[7].id]

    def test_a_question_pinned_to_one_section_cannot_surface_in_another(
        self, client: TestClient, db: Session
    ):
        """Pinning is exclusive. Otherwise 'for Section A' would mean nothing."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [make_question(db, subject, difficulty=Difficulty.EASY) for _ in range(4)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)

        a = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        _section(db, exam, "Section B", 1, RULES_ONE_EASY_MCQ)
        _pin(db, exam, questions[0], a)
        db.refresh(exam)

        for _ in range(8):  # different candidates, different draws
            other = make_user(db, role=UserRole.CANDIDATE)
            _, entries = generate_paper(exam=exam, candidate_id=other.id)
            drawn = [e.question_id for e in entries]
            assert drawn[0] == questions[0].id, "Section A must get its pinned question"
            assert drawn.count(questions[0].id) == 1, "and only Section A"

        _, entries = generate_paper(exam=exam, candidate_id=candidate.id)
        assert len(entries) == 2

    def test_unpinned_questions_stay_available_to_every_section(
        self, client: TestClient, db: Session
    ):
        """The old behaviour, kept: an unpinned pool is shared, as it always was."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [make_question(db, subject, difficulty=Difficulty.EASY) for _ in range(2)]
        exam = make_exam(db, subject, examiner, questions=questions, status=ExamStatus.DRAFT)

        _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        _section(db, exam, "Section B", 1, RULES_ONE_EASY_MCQ)
        db.refresh(exam)

        _, entries = generate_paper(exam=exam, candidate_id=candidate.id)

        drawn = {e.question_id for e in entries}
        assert drawn == {questions[0].id, questions[1].id}

    def test_sections_keep_their_order_in_the_paper(self, client: TestClient, db: Session):
        """Randomisation shuffles inside a section, never across two of them."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        first = [make_question(db, subject, difficulty=Difficulty.EASY) for _ in range(2)]
        second = [make_question(db, subject, difficulty=Difficulty.HARD) for _ in range(2)]
        exam = make_exam(
            db, subject, examiner, questions=first + second, status=ExamStatus.DRAFT
        )

        _section(
            db,
            exam,
            "Section A",
            0,
            {"rules": [{"question_type": "mcq", "difficulty": "easy", "count": 2}]},
        )
        _section(
            db,
            exam,
            "Section B",
            1,
            {"rules": [{"question_type": "mcq", "difficulty": "hard", "count": 2}]},
        )
        db.refresh(exam)

        _, entries = generate_paper(exam=exam, candidate_id=candidate.id)

        drawn = [e.question_id for e in entries]
        assert set(drawn[:2]) == {q.id for q in first}
        assert set(drawn[2:]) == {q.id for q in second}

    def test_an_exam_with_no_sections_behaves_exactly_as_before(
        self, client: TestClient, db: Session
    ):
        """Every exam built before sections existed still runs on this code path."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        subject = make_subject(db)
        questions = [make_question(db, subject, difficulty=Difficulty.EASY) for _ in range(5)]
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=questions,
            rules=[{"question_type": "mcq", "difficulty": "easy", "count": 3}],
            status=ExamStatus.DRAFT,
        )
        db.refresh(exam)

        _, entries = generate_paper(exam=exam, candidate_id=candidate.id)

        assert len(entries) == 3
        assert {e.question_id for e in entries} <= {q.id for q in questions}

    def test_a_shortfall_names_the_section_that_is_short(self, client: TestClient, db: Session):
        """'Need 2 mcq/easy' is not actionable when three sections want mcq/easy."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, difficulty=Difficulty.EASY)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)

        _section(db, exam, "Aptitude", 0, RULES_ONE_EASY_MCQ)
        _section(
            db,
            exam,
            "Reasoning",
            1,
            {"rules": [{"question_type": "mcq", "difficulty": "easy", "count": 4}]},
        )
        db.refresh(exam)

        problems = check_pool_satisfies_rules(exam)

        assert any("Reasoning" in p for p in problems), problems


class TestPinningThroughTheApi:
    def test_an_examiner_pins_a_pooled_question_to_a_section(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        headers = auth_headers(client, examiner)

        response = client.patch(
            f"/api/v1/exams/{exam.id}/questions/{question.id}/section",
            json={"section_id": str(section.id)},
            headers=headers,
        )

        assert response.status_code == 200, response.text
        entry = next(
            e for e in response.json()["entries"] if e["question_id"] == str(question.id)
        )
        assert entry["section_id"] == str(section.id)

    def test_a_pin_can_be_undone_back_to_the_shared_pool(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        headers = auth_headers(client, examiner)
        path = f"/api/v1/exams/{exam.id}/questions/{question.id}/section"

        client.patch(path, json={"section_id": str(section.id)}, headers=headers)
        response = client.patch(path, json={"section_id": None}, headers=headers)

        assert response.status_code == 200, response.text
        entry = next(
            e for e in response.json()["entries"] if e["question_id"] == str(question.id)
        )
        assert entry["section_id"] is None

    def test_a_section_from_another_exam_is_refused(self, client: TestClient, db: Session):
        """The foreign key would allow it; the question would then be drawn by nothing."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject)
        mine = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        theirs = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        foreign = _section(db, theirs, "Section A", 0, RULES_ONE_EASY_MCQ)
        headers = auth_headers(client, examiner)

        response = client.patch(
            f"/api/v1/exams/{mine.id}/questions/{question.id}/section",
            json={"section_id": str(foreign.id)},
            headers=headers,
        )

        assert response.status_code == 404

    def test_a_question_outside_the_pool_cannot_be_pinned(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        stranger = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        headers = auth_headers(client, examiner)

        response = client.patch(
            f"/api/v1/exams/{exam.id}/questions/{stranger.id}/section",
            json={"section_id": str(section.id)},
            headers=headers,
        )

        assert response.status_code == 404

    def test_questions_can_be_added_straight_into_a_section(
        self, client: TestClient, db: Session
    ):
        """What the wizard's per-section bank picker does in one call."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        questions = [make_question(db, subject) for _ in range(2)]
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        headers = auth_headers(client, examiner)

        response = client.post(
            f"/api/v1/exams/{exam.id}/questions",
            json={
                "question_ids": [str(q.id) for q in questions],
                "section_id": str(section.id),
            },
            headers=headers,
        )

        assert response.status_code == 200, response.text
        assert all(e["section_id"] == str(section.id) for e in response.json()["entries"])


class TestPinsSurviveTheWizard:
    """The wizard PATCHes the whole exam on every autosave. Pins must not be collateral."""

    def _payload(self, exam: Exam, names: list[str]) -> dict:
        return {
            "sections": [
                {
                    "name": name,
                    "order_index": index,
                    "selection_rules": RULES_ONE_EASY_MCQ,
                }
                for index, name in enumerate(names)
            ]
        }

    def test_saving_the_draft_again_keeps_the_section_and_its_pins(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        client.patch(
            f"/api/v1/exams/{exam.id}", json=self._payload(exam, ["Section A"]), headers=headers
        )
        section_id = client.get(f"/api/v1/exams/{exam.id}", headers=headers).json()["sections"][
            0
        ]["id"]
        client.patch(
            f"/api/v1/exams/{exam.id}/questions/{question.id}/section",
            json={"section_id": section_id},
            headers=headers,
        )

        # Autosave: same sections, one description edited.
        again = self._payload(exam, ["Section A"])
        again["sections"][0]["description"] = "Aptitude and reasoning"
        client.patch(f"/api/v1/exams/{exam.id}", json=again, headers=headers)

        after = client.get(f"/api/v1/exams/{exam.id}", headers=headers).json()
        assert after["sections"][0]["id"] == section_id, "the section was recreated"
        pool = client.get(f"/api/v1/exams/{exam.id}/pool", headers=headers).json()
        assert pool["entries"][0]["section_id"] == section_id

    def test_two_sections_can_swap_names_without_colliding(
        self, client: TestClient, db: Session
    ):
        """(exam_id, name) is unique, so a naive in-place rename trips halfway."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        client.patch(
            f"/api/v1/exams/{exam.id}",
            json=self._payload(exam, ["Aptitude", "Reasoning"]),
            headers=headers,
        )
        response = client.patch(
            f"/api/v1/exams/{exam.id}",
            json=self._payload(exam, ["Reasoning", "Aptitude"]),
            headers=headers,
        )

        assert response.status_code == 200, response.text
        names = [s["name"] for s in sorted(response.json()["sections"], key=lambda s: s["order_index"])]
        assert names == ["Reasoning", "Aptitude"]

    def test_removing_a_section_returns_its_questions_to_the_pool(
        self, client: TestClient, db: Session
    ):
        """A question an examiner wrote must not be deleted by a layout change."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject)
        exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        client.patch(
            f"/api/v1/exams/{exam.id}",
            json=self._payload(exam, ["Section A", "Section B"]),
            headers=headers,
        )
        sections = client.get(f"/api/v1/exams/{exam.id}", headers=headers).json()["sections"]
        second = sorted(sections, key=lambda s: s["order_index"])[1]["id"]
        client.patch(
            f"/api/v1/exams/{exam.id}/questions/{question.id}/section",
            json={"section_id": second},
            headers=headers,
        )

        client.patch(
            f"/api/v1/exams/{exam.id}",
            json=self._payload(exam, ["Section A"]),
            headers=headers,
        )

        db.expire_all()
        entry = db.scalar(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id))
        assert entry is not None, "the question was deleted with its section"
        assert entry.section_id is None, "it should be back in the shared pool"
        assert db.scalar(select(Exam).where(Exam.id == exam.id)) is not None


class TestPinnedMarksAndTypes:
    def test_a_pin_does_not_excuse_a_question_from_its_section_rule(
        self, client: TestClient, db: Session
    ):
        """Pinning says which section, not which type. A mismatch is still a shortfall."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        wrong_type = make_question(
            db, subject, qtype=QuestionType.SHORT_ANSWER, difficulty=Difficulty.EASY
        )
        exam = make_exam(db, subject, examiner, questions=[wrong_type], status=ExamStatus.DRAFT)
        section = _section(db, exam, "Section A", 0, RULES_ONE_EASY_MCQ)
        _pin(db, exam, wrong_type, section)
        db.refresh(exam)

        problems = check_pool_satisfies_rules(exam)

        assert problems, "an mcq rule cannot be satisfied by a short answer"
