"""Topic-level performance analysis, for the examiner and for the candidate themselves.

One builder, two audiences, and the difference between them is a single flag that
matters a great deal.

An examiner may look at everything, including a paper whose result has not been
released. A candidate may not: their own analysis has to be built from the marks they
have actually been given, or the narrative leaks scores an examiner has not published
yet. "You are weakest in Normalisation" computed from an unreleased paper tells the
candidate their mark on that paper by implication.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.db.models import Answer, ExamSession, Question, Result, User

#: A topic needs at least this many marked answers before it says anything about a
#: candidate. One question they happened to get wrong is not a weakness.
MIN_ANSWERS_PER_TOPIC = 2

#: Above this, a topic is a strength; below the lower bound, it needs work. The gap
#: between them is deliberate - a topic at 60% is neither, and saying nothing about it
#: is more useful than forcing it into a bucket.
STRONG_AT = 70.0
WEAK_BELOW = 50.0

MAX_LISTED = 5


@dataclass(frozen=True)
class TopicScore:
    topic: str
    percentage: float
    answers: int


@dataclass(frozen=True)
class Analysis:
    candidate_id: uuid.UUID
    candidate_name: str
    overall_percentage: float
    strong_areas: list[str]
    weak_areas: list[str]
    recommendations: list[str]
    summary: str
    topic_scores: list[TopicScore]
    generated_at: datetime


def topic_scores(
    db: Session, candidate_id: uuid.UUID, *, published_only: bool
) -> list[TopicScore]:
    """Average score per topic, best first.

    ``published_only`` restricts the data to sittings whose result has been released -
    which is what the candidate's own view must use.
    """
    ratio = cast(Answer.awarded_marks, Float) / func.nullif(Answer.max_marks, 0)

    stmt = (
        select(Question.topic, func.count(Answer.id), func.avg(ratio) * 100)
        .join(Answer, Answer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == Answer.session_id)
        .where(
            ExamSession.candidate_id == candidate_id,
            Question.topic.is_not(None),
            Answer.awarded_marks.is_not(None),
        )
        .group_by(Question.topic)
        .having(func.count(Answer.id) >= MIN_ANSWERS_PER_TOPIC)
        .order_by(func.avg(ratio).desc())
    )
    if published_only:
        stmt = stmt.join(Result, Result.session_id == ExamSession.id).where(
            Result.published.is_(True)
        )

    return [
        TopicScore(topic=topic, percentage=round(float(average or 0.0), 1), answers=int(count))
        for topic, count, average in db.execute(stmt).all()
        if topic
    ]


def analyse(db: Session, candidate: User, *, published_only: bool) -> Analysis:
    """Build the narrative. Says less when it knows less."""
    scores = topic_scores(db, candidate.id, published_only=published_only)

    overall = (
        db.scalar(
            select(func.avg(Result.percentage))
            .join(ExamSession, ExamSession.id == Result.session_id)
            .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
        )
        or 0.0
    )
    overall = round(float(overall), 2)

    strong = [s.topic for s in scores if s.percentage >= STRONG_AT][:MAX_LISTED]
    # Worst first, so the most urgent gap is named first.
    weak = [s.topic for s in reversed(scores) if s.percentage < WEAK_BELOW][:MAX_LISTED]

    recommendations = [f"Practise more problems in {topic}." for topic in weak]

    published_count = (
        db.scalar(
            select(func.count(Result.id))
            .join(ExamSession, ExamSession.id == Result.session_id)
            .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
        )
        or 0
    )

    # Nothing marked and nothing published: there is genuinely no analysis to give, and
    # reporting "0%" would read as a score rather than an absence.
    if not scores and not published_count:
        return Analysis(
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            overall_percentage=0.0,
            strong_areas=[],
            weak_areas=[],
            recommendations=["Sit an exam to see your analysis here."],
            summary="No results have been published yet, so there is nothing to analyse.",
            topic_scores=[],
            generated_at=datetime.now(UTC),
        )

    parts: list[str] = []
    if not published_count:
        # Reachable only on the staff view, which can see marked-but-unreleased work.
        # There are topic scores to report, but no published overall to report them
        # against - and quoting 0% here would look like the candidate scored nothing.
        parts.append("No results have been published yet, so there is no overall score.")
    elif overall >= 80:
        parts.append(f"Outstanding overall performance at {overall:.1f}%.")
    elif overall >= 60:
        parts.append(f"Solid overall performance at {overall:.1f}%.")
    else:
        parts.append(f"Overall performance is {overall:.1f}% — there is clear room to grow.")

    if strong:
        parts.append(f"Strongest in {', '.join(strong[:3])}.")
    if weak:
        parts.append(f"Most room for improvement in {', '.join(weak[:3])}.")
    if not scores:
        # Marks exist, but not enough per topic to say anything specific about any of
        # them. Better to admit that than to name a "weakness" from one answer.
        parts.append(
            f"Not enough answers per topic yet to break this down — "
            f"a topic needs at least {MIN_ANSWERS_PER_TOPIC} marked answers."
        )
    if not recommendations:
        recommendations.append("Keep practice consistent across topics.")

    return Analysis(
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        overall_percentage=overall,
        strong_areas=strong,
        weak_areas=weak,
        recommendations=recommendations,
        summary=" ".join(parts),
        topic_scores=scores,
        generated_at=datetime.now(UTC),
    )
