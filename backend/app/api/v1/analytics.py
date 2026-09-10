"""Exam analytics and candidate performance analysis."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Float, and_, case, cast, func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentCandidate, CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.db.models import (
    Answer,
    Exam,
    ExamSession,
    GradeStatus,
    Question,
    Result,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas.analytics import (
    DifficultyBreakdown,
    ExamAnalytics,
    PerformanceAnalysis,
    SectionAnalytics,
    TopicPerformance,
    TopicScoreOut,
)
from app.services import live_operations, performance

router = APIRouter(tags=["analytics"])
logger = get_logger("analytics")


@dataclass(frozen=True)
class _GroupStats:
    """Answer counts for one bucket of questions - one difficulty, or one topic."""

    group: object
    total: int
    correct: int
    incorrect: int
    unanswered: int
    avg_pct: float


def _grouped_answer_stats(
    db, exam_id: uuid.UUID, column, *, limit: int | None = None
) -> list[_GroupStats]:
    """Aggregate an exam's answers by any question column.

    Shared by the difficulty and topic breakdowns because the arithmetic is identical
    and only the grouping column differs. A blank answer is counted as unanswered rather
    than incorrect - the distinction is the whole point of these two reports, since "did
    not attempt" and "got it wrong" call for different teaching.
    """
    answered = Answer.grade_status != GradeStatus.UNANSWERED
    rows = db.execute(
        select(
            column.label("group"),
            func.count(Answer.id).label("total"),
            func.count(
                case((and_(answered, Answer.awarded_marks >= Answer.max_marks), 1))
            ).label("correct"),
            func.count(case((Answer.grade_status == GradeStatus.UNANSWERED, 1))).label(
                "unanswered"
            ),
            func.avg(
                case(
                    (
                        answered,
                        # Floored at zero to match compute_result's policy that negative
                        # marking cannot push a script below nothing. Without this the
                        # same paper reports a negative percentage here and a floored
                        # one on the result page.
                        func.greatest(
                            func.cast(Answer.awarded_marks, Float)
                            / func.nullif(Answer.max_marks, 0)
                            * 100,
                            0.0,
                        ),
                    )
                )
            ).label("avg_pct"),
        )
        .join(Answer, Answer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == Answer.session_id)
        .where(ExamSession.exam_id == exam_id)
        .group_by(column)
        .order_by(func.count(Answer.id).desc())
        .limit(limit)
    ).all()

    return [
        _GroupStats(
            group=row.group,
            total=row.total,
            correct=row.correct,
            # Whatever is left once the correct and the untouched are accounted for.
            incorrect=max(0, row.total - row.correct - row.unanswered),
            unanswered=row.unanswered,
            avg_pct=round(float(row.avg_pct or 0), 2),
        )
        for row in rows
    ]


# -------------------------------------------------------- exam analytics


@router.get("/exams/{exam_id}/analytics", response_model=ExamAnalytics)
def exam_analytics(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamAnalytics:
    """Aggregate performance statistics for one exam."""
    exam = db.scalar(
        select(Exam).where(Exam.id == exam_id).options(selectinload(Exam.sections))
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Basic session counts
    total_sessions = db.scalar(
        select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam_id)
    ) or 0
    completed_sessions = db.scalar(
        select(func.count(ExamSession.id)).where(
            ExamSession.exam_id == exam_id,
            ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.AUTO_SUBMITTED]),
        )
    ) or 0

    # Score aggregates from results
    result_agg = db.execute(
        select(
            func.avg(Result.percentage),
            func.max(Result.percentage),
            func.min(Result.percentage),
        )
        .join(ExamSession, ExamSession.id == Result.session_id)
        .where(ExamSession.exam_id == exam_id)
    ).one()

    avg_pct = float(result_agg[0] or 0)
    highest_pct = float(result_agg[1] or 0)
    lowest_pct = float(result_agg[2] or 0)

    # Pass rate. An exam with no declared pass mark has no pass rate - reporting one
    # against an invented threshold is how the same cohort reads differently on two
    # screens. Zero here means "nobody passed"; the absent mark means "no verdict".
    if exam.passing_percentage is None:
        pass_rate = None
    else:
        passing_count = (
            db.scalar(
                select(func.count(Result.id))
                .join(ExamSession, ExamSession.id == Result.session_id)
                .where(
                    ExamSession.exam_id == exam_id,
                    Result.percentage >= exam.passing_percentage,
                )
            )
            or 0
        )
        pass_rate = (
            round(passing_count / completed_sessions * 100, 2) if completed_sessions else 0.0
        )

    # All percentages for distribution
    score_distribution = [
        float(row[0])
        for row in db.execute(
            select(Result.percentage)
            .join(ExamSession, ExamSession.id == Result.session_id)
            .where(ExamSession.exam_id == exam_id)
        ).all()
    ]

    difficulty_breakdown = [
        DifficultyBreakdown(
            difficulty=row.group,
            total_questions=row.total,
            correct=row.correct,
            incorrect=row.incorrect,
            unanswered=row.unanswered,
            avg_score_pct=row.avg_pct,
        )
        for row in _grouped_answer_stats(db, exam_id, Question.difficulty)
        if row.group is not None
    ]

    topic_performance = [
        TopicPerformance(
            topic=row.group,
            total_questions=row.total,
            correct=row.correct,
            incorrect=row.incorrect,
            avg_score_pct=row.avg_pct,
        )
        for row in _grouped_answer_stats(db, exam_id, Question.topic, limit=20)
        if row.group
    ]

    # Section analytics (corporate exams)
    section_analytics: list[SectionAnalytics] = []
    if exam.sections:
        for section in sorted(exam.sections, key=lambda s: s.order_index):
            sec_agg = db.execute(
                select(
                    func.sum(Answer.max_marks),
                    func.avg(cast(Answer.awarded_marks, Float)),
                    func.avg(
                        cast(Answer.awarded_marks, Float)
                        / func.nullif(Answer.max_marks, 0)
                        * 100
                    ),
                    func.count(Answer.id),
                )
                .join(ExamSession, ExamSession.id == Answer.session_id)
                .where(ExamSession.exam_id == exam_id, Answer.section_id == section.id)
            ).one()

            # Same rule as the exam-level rate: without a declared pass mark there is
            # no threshold to measure a section against.
            if exam.passing_percentage is None:
                section_pass_rate = None
            else:
                sec_pass = (
                    db.scalar(
                        select(func.count(ExamSession.id.distinct()))
                        .join(Answer, Answer.session_id == ExamSession.id)
                        .where(
                            ExamSession.exam_id == exam_id, Answer.section_id == section.id
                        )
                        .having(
                            func.avg(
                                cast(Answer.awarded_marks, Float)
                                / func.nullif(Answer.max_marks, 0)
                            )
                            >= (exam.passing_percentage / 100)
                        )
                    )
                    or 0
                )
                section_pass_rate = (
                    round(sec_pass / completed_sessions * 100, 2) if completed_sessions else 0.0
                )

            section_analytics.append(
                SectionAnalytics(
                    section_name=section.name,
                    total_marks=float(sec_agg[0] or 0),
                    avg_obtained=round(float(sec_agg[1] or 0), 2),
                    avg_percentage=round(float(sec_agg[2] or 0), 2),
                    pass_rate=section_pass_rate,
                )
            )

    return ExamAnalytics(
        exam_id=exam.id,
        exam_title=exam.title,
        exam_type=exam.exam_type.value,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        avg_percentage=round(avg_pct, 2),
        highest_percentage=round(highest_pct, 2),
        lowest_percentage=round(lowest_pct, 2),
        pass_rate=pass_rate,
        difficulty_breakdown=difficulty_breakdown,
        topic_performance=topic_performance,
        section_analytics=section_analytics,
        score_distribution=score_distribution,
    )


# ------------------------------------------------ candidate performance


def _to_analysis_out(analysis: performance.Analysis) -> PerformanceAnalysis:
    return PerformanceAnalysis(
        candidate_id=analysis.candidate_id,
        candidate_name=analysis.candidate_name,
        overall_percentage=analysis.overall_percentage,
        strong_areas=analysis.strong_areas,
        weak_areas=analysis.weak_areas,
        recommendations=analysis.recommendations,
        summary=analysis.summary,
        section_notes=[],
        topic_scores=[
            TopicScoreOut(topic=score.topic, percentage=score.percentage, answers=score.answers)
            for score in analysis.topic_scores
        ],
        generated_at=analysis.generated_at,
    )


@router.get(
    "/candidates/{candidate_id}/performance-analysis",
    response_model=PerformanceAnalysis,
)
def candidate_performance_analysis(
    candidate_id: uuid.UUID, staff: CurrentStaff, db: DbSession
) -> PerformanceAnalysis:
    """Narrative performance analysis for one candidate, for staff.

    Built from every marked answer, published or not - an examiner reviewing a
    candidate is entitled to the work in front of them. The candidate's own view of
    this is deliberately narrower; see ``my_performance_analysis``.

    The platform assists assessment. It does not make academic or hiring decisions.
    """
    candidate = db.get(User, candidate_id)
    if candidate is None or candidate.role is not UserRole.CANDIDATE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    return _to_analysis_out(performance.analyse(db, candidate, published_only=False))


@router.get("/my/performance-analysis", response_model=PerformanceAnalysis)
def my_performance_analysis(
    candidate: CurrentCandidate, db: DbSession
) -> PerformanceAnalysis:
    """The candidate's own analysis, from their released marks only.

    ``published_only`` is the whole difference between this and the staff view. An
    analysis built over unpublished papers would leak their marks by implication - being
    told you are weakest in Normalisation is being told roughly how you did on the paper
    that covered it, before an examiner has released it.
    """
    return _to_analysis_out(performance.analyse(db, candidate, published_only=True))


# ------------------------------------------------ live operations dashboard


@router.get("/analytics/live-dashboard")
def live_dashboard_telemetry(staff: CurrentStaff, db: DbSession) -> dict:
    """Everything happening across this examiner's exams right now.

    Read entirely from the database - see :mod:`app.services.live_operations` for why
    that is worth saying out loud. A quiet platform reports zeros.
    """
    return live_operations.build(db, staff)


