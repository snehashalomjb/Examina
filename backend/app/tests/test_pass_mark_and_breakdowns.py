"""Pass/fail verdicts, and the difficulty/topic breakdowns behind them.

Two rules under test. First, an exam that never declared a pass mark has no verdict -
the platform reports the score and stops, rather than inventing a threshold, which is
how the same script used to read as a pass on one screen and a fail on another. Second,
a blank answer is unanswered, not wrong: "did not attempt" and "got it wrong" call for
different teaching, and a report that conflates them is useless for both.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.api.v1.analytics import _grouped_answer_stats
from app.db.models import (
    AccessStatus,
    Answer,
    Difficulty,
    ExamSession,
    GradeStatus,
    Question,
    QuestionType,
    SessionStatus,
    UserRole,
)
from app.services import exam_engine
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)

API = "/api/v1"


class TestThePassRule:
    def test_no_declared_mark_means_no_verdict(self, db):
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER)
        exam = make_exam(
            db, subject, examiner, questions=[make_question(db, subject)]
        )
        exam.passing_percentage = None
        db.flush()

        # Not False - there is nothing to be false about.
        assert exam_engine.passed(0.0, exam) is None
        assert exam_engine.passed(100.0, exam) is None

    @pytest.mark.parametrize(
        ("percentage", "expected"),
        [(39.9, False), (40.0, True), (40.1, True), (0.0, False), (100.0, True)],
    )
    def test_a_declared_mark_is_inclusive(self, db, percentage, expected):
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER)
        exam = make_exam(db, subject, examiner, questions=[make_question(db, subject)])
        exam.passing_percentage = 40.0
        db.flush()

        # Scoring exactly the pass mark is a pass, not a fail.
        assert exam_engine.passed(percentage, exam) is expected


class TestTheCandidateSeesTheVerdict:
    @pytest.fixture
    def published(self, client, db):
        """One candidate with a published result on an exam with a 40% pass mark."""
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        candidate = make_user(db, role=UserRole.CANDIDATE)
        mcqs = [
            make_question(
                db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY, marks=2.0
            )
            for _ in range(2)
        ]
        exam = make_exam(
            db,
            subject,
            examiner,
            questions=mcqs,
            candidates=[candidate],
            rules=[{"question_type": "mcq", "difficulty": "easy", "count": 2}],
        )
        exam.passing_percentage = 40.0
        db.flush()

        candidate_headers = auth_headers(client, candidate)
        paper = client.post(
            f"{API}/exams/{exam.id}/start", headers=candidate_headers
        ).json()
        exam_headers = {**candidate_headers, "X-Exam-Token": paper["exam_token"]}
        questions = {q.id: q for q in mcqs}
        for item in paper["questions"]:
            question = questions[uuid.UUID(item["question_id"])]
            client.put(
                f"{API}/sessions/{paper['session_id']}/answers/{item['question_id']}",
                headers=exam_headers,
                json={
                    "selected_option_ids": [
                        str(o.id) for o in question.options if o.is_correct
                    ]
                },
            )
        client.post(f"{API}/sessions/{paper['session_id']}/submit", headers=exam_headers)
        client.post(
            f"{API}/sessions/{paper['session_id']}/result/publish",
            headers=auth_headers(client, examiner),
        )
        return {"candidate_headers": candidate_headers, "exam": exam, "subject": subject}

    def test_a_published_result_carries_its_verdict_and_context(self, client, published):
        rows = client.get(f"{API}/my/results", headers=published["candidate_headers"]).json()
        assert len(rows) == 1
        row = rows[0]

        # A bare percentage on a dashboard row is unreadable without these.
        assert row["exam_title"] == published["exam"].title
        assert row["subject_name"] == published["subject"].name
        assert row["passing_percentage"] == 40.0
        assert row["passed"] is True
        assert row["percentage"] == 100.0

    def test_no_pass_mark_yields_a_null_verdict_not_a_failure(self, client, db, published):
        published["exam"].passing_percentage = None
        db.flush()

        row = client.get(
            f"{API}/my/results", headers=published["candidate_headers"]
        ).json()[0]
        assert row["passed"] is None
        assert row["passing_percentage"] is None
        # The score itself is still reported.
        assert row["percentage"] == 100.0


class TestGroupedBreakdowns:
    """These previously returned an empty list regardless of the data."""

    @pytest.fixture
    def graded(self, db):
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER)
        candidate = make_user(db, role=UserRole.CANDIDATE)

        easy = make_question(
            db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.EASY,
            marks=2.0, negative=1.0, topic="Recursion",
        )
        hard = make_question(
            db, subject, qtype=QuestionType.MCQ, difficulty=Difficulty.HARD,
            marks=2.0, negative=1.0, topic="Recursion",
        )
        exam = make_exam(db, subject, examiner, questions=[easy, hard])

        session = ExamSession(
            exam_id=exam.id,
            candidate_id=candidate.id,
            paper_seed="seed",
            question_order=[],
            started_at=datetime.now(UTC),
            expires_at=datetime.now(UTC),
            status=SessionStatus.SUBMITTED,
        )
        db.add(session)
        db.flush()

        # One full marks, one blank, one penalised into the negative.
        db.add_all(
            [
                Answer(
                    session_id=session.id, question_id=easy.id, max_marks=2.0,
                    awarded_marks=2.0, grade_status=GradeStatus.AUTO_SCORED,
                ),
                Answer(
                    session_id=session.id, question_id=hard.id, max_marks=2.0,
                    awarded_marks=-1.0, grade_status=GradeStatus.AUTO_SCORED,
                ),
            ]
        )
        db.flush()
        return {"exam": exam, "easy": easy, "hard": hard}

    def test_the_difficulty_breakdown_is_populated(self, db, graded):
        stats = {
            row.group: row
            for row in _grouped_answer_stats(db, graded["exam"].id, Question.difficulty)
        }
        assert set(stats) == {Difficulty.EASY, Difficulty.HARD}
        assert stats[Difficulty.EASY].correct == 1
        assert stats[Difficulty.EASY].avg_pct == 100.0

    def test_negative_marking_never_reports_a_negative_percentage(self, db, graded):
        # compute_result floors a script at zero; these reports must agree with it, or
        # the same paper shows a negative percentage here and a floored one there.
        stats = {
            row.group: row
            for row in _grouped_answer_stats(db, graded["exam"].id, Question.difficulty)
        }
        assert stats[Difficulty.HARD].avg_pct == 0.0
        assert stats[Difficulty.HARD].correct == 0
        assert stats[Difficulty.HARD].incorrect == 1

    def test_a_blank_answer_counts_as_unanswered_not_incorrect(self, db, graded):
        blank = make_question(
            db, graded["exam"].subject, qtype=QuestionType.MCQ,
            difficulty=Difficulty.MEDIUM, marks=2.0,
        )
        session_id = db.scalar(
            select(ExamSession.id).where(ExamSession.exam_id == graded["exam"].id)
        )
        db.add(
            Answer(
                session_id=session_id, question_id=blank.id, max_marks=2.0,
                awarded_marks=0.0, grade_status=GradeStatus.UNANSWERED,
            )
        )
        db.flush()

        stats = {
            row.group: row
            for row in _grouped_answer_stats(db, graded["exam"].id, Question.difficulty)
        }
        medium = stats[Difficulty.MEDIUM]
        assert medium.unanswered == 1
        assert medium.incorrect == 0

    def test_grouping_by_topic_works_off_the_same_helper(self, db, graded):
        stats = _grouped_answer_stats(db, graded["exam"].id, Question.topic)
        by_topic = {row.group: row for row in stats}
        assert by_topic["Recursion"].total == 2
        assert by_topic["Recursion"].correct == 1


class TestAnalyticsEndpoint:
    def test_pass_rate_is_null_when_no_mark_is_declared(self, client, db):
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        exam = make_exam(db, subject, examiner, questions=[make_question(db, subject)])
        exam.passing_percentage = None
        db.flush()

        body = client.get(
            f"{API}/exams/{exam.id}/analytics", headers=auth_headers(client, examiner)
        ).json()
        # None means "this exam never said what passing was" - not "nobody passed".
        assert body["pass_rate"] is None
