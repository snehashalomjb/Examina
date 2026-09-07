"""Unit tests for PDF generation and scorecard export."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.db.models.enums import GradeStatus, QuestionType
from app.schemas.exam_session import (
    QuestionResult,
    ResultDetail,
    ResultOut,
    SectionScore,
)
from app.services.pdf_generator import generate_result_pdf


def test_generate_result_pdf_structure():
    """Verifies that generate_result_pdf produces valid non-empty PDF binary bytes."""
    res_id = uuid.uuid4()
    session_id = uuid.uuid4()
    q1_id = uuid.uuid4()
    q2_id = uuid.uuid4()

    result_out = ResultOut(
        id=res_id,
        session_id=session_id,
        total_marks=20.0,
        obtained_marks=16.0,
        percentage=80.0,
        correct_count=1,
        incorrect_count=0,
        unanswered_count=0,
        pending_review_count=0,
        published=True,
        published_at=datetime.now(UTC),
    )

    questions = [
        QuestionResult(
            question_id=q1_id,
            body="Explain the concept of QuickSort pivot selection strategy.",
            question_type=QuestionType.SHORT_ANSWER,
            marks=10.0,
            awarded_marks=8.0,
            grade_status=GradeStatus.EXAMINER_REVIEWED,
            is_correct=None,
            your_answer="Median of three approach chooses the median of first, middle, and last elements.",
            correct_answer="Median-of-three strategy avoids worst case O(n^2) runtime.",
            examiner_comment="Good explanation with correct time complexity note.",
            section_name="Core Algorithms",
            ai_justification="Accurate explanation of median of three strategy.",
        ),
        QuestionResult(
            question_id=q2_id,
            body="Which data structure provides O(1) average lookup time?",
            question_type=QuestionType.MCQ,
            marks=10.0,
            awarded_marks=10.0,
            grade_status=GradeStatus.AUTO_SCORED,
            is_correct=True,
            your_answer="Hash Table",
            correct_answer="Hash Table",
            examiner_comment=None,
            section_name="Core Algorithms",
            ai_justification=None,
        ),
    ]

    section_scores = [
        SectionScore(
            section_id=uuid.uuid4(),
            section_name="Core Algorithms",
            total_marks=20.0,
            obtained_marks=16.0,
            percentage=80.0,
            correct=1,
            incorrect=0,
            unanswered=0,
        )
    ]

    detail = ResultDetail(
        result=result_out,
        exam_title="Advanced Algorithms & Data Structures",
        subject_name="Computer Science",
        candidate_name="Priya Sharma",
        submitted_at=datetime.now(UTC),
        questions=questions,
        section_scores=section_scores,
        exam_type="academic",
        passing_percentage=50.0,
        percentile=94.5,
        cohort_size=45,
        time_taken_seconds=2700,
    )

    pdf_bytes = generate_result_pdf(detail, candidate_email="priya.sharma@example.com")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    # PDF magic number header
    assert pdf_bytes.startswith(b"%PDF-")
