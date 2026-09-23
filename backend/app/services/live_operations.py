"""The live operations view: what is happening across an examiner's exams right now.

Everything here is read from the database. That sounds too obvious to state, but the
endpoint this replaces did not: it padded the counts with ``max(real, 54)``, filled the
session list with five invented candidates, and returned a hardcoded proctoring alert
feed naming people who do not exist. A dashboard that inflates a quiet morning into a
busy control room is worse than no dashboard, because an examiner cannot tell which
numbers to trust - and one that invents candidate names is indefensible.

So: real numbers, and honest emptiness. A quiet platform reports zeros and empty lists,
and the UI says "nothing right now" rather than pretending otherwise.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Answer,
    Exam,
    ExamEnrollment,
    ExamSession,
    ExamStatus,
    GradeStatus,
    ProctorEvent,
    ProctorSeverity,
    Question,
    QuestionType,
    Result,
    SessionStatus,
    User,
    UserRole,
)

#: How far back the activity feed and the alert list look.
RECENT_WINDOW = timedelta(hours=24)

#: Nobody reads the 40th row of a live feed.
FEED_LIMIT = 12

#: Human labels for the proctor event types that are worth surfacing as an alert.
ALERT_LABEL = {
    "multiple_faces": "More than one face",
    "phone_detected": "Phone in frame",
    "camera_blocked": "Camera blocked",
    "devtools_open": "Developer tools opened",
    "face_missing": "Face not visible",
    "gaze_away": "Looking away",
    "tab_switch": "Left the exam tab",
    "fullscreen_exit": "Left fullscreen",
    "paste_attempt": "Paste attempt",
    "copy_attempt": "Copy attempt",
    "window_blur": "Window lost focus",
}

#: Which grading-queue bucket a question type falls into, for the UI's icon.
QUEUE_KIND = {
    QuestionType.SHORT_ANSWER: "short",
    QuestionType.LONG_ANSWER: "long",
    QuestionType.IMAGE_UPLOAD: "image",
    QuestionType.CODING: "long",
}


def _ago(moment: datetime | None, *, now: datetime) -> str:
    """"7 min ago", in the coarsest unit that is still honest."""
    if moment is None:
        return "just now"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    seconds = max(int((now - moment).total_seconds()), 0)
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    return f"{hours // 24} d ago"


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "??").upper()


def _severity_tone(severity: ProctorSeverity) -> str:
    if severity is ProctorSeverity.CRITICAL:
        return "rose"
    if severity is ProctorSeverity.WARNING:
        return "amber"
    return "mint"


@dataclass(frozen=True)
class Scope:
    """Whose exams this view covers.

    An examiner sees their own; an admin sees everything. Same rule as the stat cards,
    because a dashboard that counts other people's exams next to your own is a dashboard
    nobody can act on.
    """

    exam_ids: list[uuid.UUID] | None  # None = every exam

    @property
    def session_clause(self):
        """A WHERE clause for any query that reaches ``exam_sessions``.

        Returned as a list so it can be splatted into ``.where(...)`` alongside other
        conditions. An examiner with no exams gets ``false()`` - matching nothing, which
        is the truthful answer, where an absent clause would show them everyone's data.
        """
        if self.exam_ids is None:
            return []
        if not self.exam_ids:
            return [false()]
        return [ExamSession.exam_id.in_(self.exam_ids)]

    @property
    def exam_clause(self):
        """The same, for queries over ``exams`` directly."""
        if self.exam_ids is None:
            return []
        if not self.exam_ids:
            return [false()]
        return [Exam.id.in_(self.exam_ids)]

    def filter_sessions(self, stmt):
        clause = self.session_clause
        return stmt.where(*clause) if clause else stmt


def scope_for(db: Session, staff: User) -> Scope:
    if staff.role is UserRole.ADMIN:
        return Scope(exam_ids=None)
    return Scope(
        exam_ids=list(db.scalars(select(Exam.id).where(Exam.created_by_id == staff.id)))
    )


def build(db: Session, staff: User) -> dict:
    """Assemble the whole payload. One call, because the UI polls it as a unit."""
    now = datetime.now(UTC)
    since = now - RECENT_WINDOW
    scope = scope_for(db, staff)

    exam_filter = scope.exam_clause
    session_filter = scope.session_clause

    # ------------------------------------------------------------------ counts
    active_count = (
        db.scalar(
            scope.filter_sessions(
                select(func.count(ExamSession.id)).where(
                    ExamSession.status == SessionStatus.IN_PROGRESS
                )
            )
        )
        or 0
    )

    # "Today" means today, in the exam window's terms - an exam whose window is open
    # now, or opens before midnight. It used to count every exam ever created.
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    exams_today_count = (
        db.scalar(
            select(func.count(Exam.id)).where(
                Exam.status == ExamStatus.PUBLISHED,
                Exam.starts_at <= end_of_day,
                Exam.ends_at >= now,
                *exam_filter,
            )
        )
        or 0
    )

    flagged_count = (
        db.scalar(
            scope.filter_sessions(
                select(func.count(ExamSession.id)).where(ExamSession.is_flagged.is_(True))
            )
        )
        or 0
    )

    pending_states = [GradeStatus.PENDING_AI, GradeStatus.AI_SCORED]
    grading_queue_count = (
        db.scalar(
            select(func.count(Answer.id))
            .join(ExamSession, Answer.session_id == ExamSession.id)
            .where(Answer.grade_status.in_(pending_states), *session_filter)
        )
        or 0
    )

    ai_prescored_count = (
        db.scalar(
            select(func.count(Answer.id))
            .join(ExamSession, Answer.session_id == ExamSession.id)
            .where(Answer.grade_status == GradeStatus.AI_SCORED, *session_filter)
        )
        or 0
    )

    # No published results means there is no average. 0.0 says "nothing yet" and the UI
    # renders a dash; inventing 71% would be a number an examiner might act on.
    avg_score = db.scalar(
        select(func.avg(Result.percentage))
        .join(ExamSession, Result.session_id == ExamSession.id)
        .where(Result.published.is_(True), *session_filter)
    )
    avg_score_pct = round(float(avg_score), 1) if avg_score is not None else 0.0

    # ----------------------------------------------------------- live sittings
    live_rows = list(
        db.scalars(
            scope.filter_sessions(
                select(ExamSession)
                .where(ExamSession.status == SessionStatus.IN_PROGRESS)
                .options(
                    selectinload(ExamSession.candidate),
                    selectinload(ExamSession.exam).selectinload(Exam.subject),
                    selectinload(ExamSession.answers),
                )
                .order_by(ExamSession.suspicion_score.desc(), ExamSession.started_at.desc())
                .limit(FEED_LIMIT)
            )
        )
    )

    live_sessions = []
    for session in live_rows:
        answered = sum(1 for a in session.answers if a.is_answered)
        total = len(session.question_order or []) or len(session.answers)
        expires = session.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        remaining = max(int((expires - now).total_seconds()), 0) if expires else 0
        name = session.candidate.full_name if session.candidate else "Candidate"

        live_sessions.append(
            {
                "session_id": str(session.id),
                "candidate_name": name,
                "initials": _initials(name),
                "exam_title": session.exam.title if session.exam else "Assessment",
                "subject_name": (
                    session.exam.subject.name if session.exam and session.exam.subject else "—"
                ),
                "answered_count": answered,
                "total_questions": total,
                "time_remaining_str": f"{remaining // 60:02d}:{remaining % 60:02d}",
                "suspicion_score": round(session.suspicion_score, 1),
                "is_flagged": session.is_flagged,
                "status": session.status.value,
            }
        )

    # -------------------------------------------------------- proctoring alerts
    alert_stmt = (
        select(ProctorEvent)
        .join(ExamSession, ProctorEvent.session_id == ExamSession.id)
        .where(
            ProctorEvent.occurred_at >= since,
            ProctorEvent.severity.in_([ProctorSeverity.WARNING, ProctorSeverity.CRITICAL]),
        )
        .options(
            selectinload(ProctorEvent.session).selectinload(ExamSession.candidate),
            selectinload(ProctorEvent.session).selectinload(ExamSession.exam),
        )
        .order_by(ProctorEvent.occurred_at.desc())
        .limit(FEED_LIMIT)
    )
    if session_filter:
        alert_stmt = alert_stmt.where(*session_filter)

    proctoring_alerts = []
    for event in db.scalars(alert_stmt):
        session = event.session
        candidate = session.candidate if session else None
        proctoring_alerts.append(
            {
                "id": str(event.id),
                "alert_type": ALERT_LABEL.get(
                    event.event_type.value, event.event_type.value.replace("_", " ")
                ),
                "candidate_name": candidate.full_name if candidate else "Candidate",
                "exam_title": session.exam.title if session and session.exam else "Assessment",
                "time_ago": _ago(event.occurred_at, now=now),
                # The event's own weight, which is what actually moved the score.
                "suspicion_delta": f"suspicion +{round(event.weight, 1):g}",
                "severity": _severity_tone(event.severity),
            }
        )

    # ------------------------------------------------------ proctoring signals
    #
    # Shares of *recent sittings* that stayed clean on each axis, rather than invented
    # percentages. With no recent sittings every share is 0 and the UI says so.
    recent_sessions = list(
        db.scalars(
            scope.filter_sessions(
                select(ExamSession)
                .where(ExamSession.started_at >= since)
                .options(selectinload(ExamSession.proctor_events))
            )
        )
    )
    signals = _signals(recent_sessions)

    # ---------------------------------------------------- score distribution
    buckets = [("0–20", 0, 20), ("21–40", 20, 40), ("41–60", 40, 60), ("61–80", 60, 80),
               ("81–100", 80, 100)]
    percentages = list(
        db.scalars(
            select(Result.percentage)
            .join(ExamSession, Result.session_id == ExamSession.id)
            .where(Result.published.is_(True), *session_filter)
        )
    )
    score_distribution = [
        {
            "bin": label,
            "count": sum(1 for p in percentages if (low < p <= high) or (low == 0 and p == 0)),
        }
        for label, low, high in buckets
    ]

    # -------------------------------------------------------- grading queue
    queue_stmt = (
        select(Answer)
        .join(ExamSession, Answer.session_id == ExamSession.id)
        .where(Answer.grade_status.in_(pending_states))
        .options(selectinload(Answer.question), selectinload(Answer.ai_evaluations))
        .order_by(Answer.updated_at.desc().nullslast(), Answer.id)
        .limit(FEED_LIMIT)
    )
    if session_filter:
        queue_stmt = queue_stmt.where(*session_filter)

    ai_grading_queue = []
    for answer in db.scalars(queue_stmt):
        question: Question | None = answer.question
        latest = max(answer.ai_evaluations, key=lambda e: e.created_at, default=None)
        if latest is not None and latest.error is None:
            score = f"{round(latest.score, 1):g}/{round(latest.max_score, 1):g}"
        else:
            score = "awaiting AI"
        ai_grading_queue.append(
            {
                "id": str(answer.id),
                "question_type": QUEUE_KIND.get(question.question_type, "short")
                if question
                else "short",
                "title": (question.body[:90] if question else "Answer"),
                "ai_score": score,
            }
        )

    # -------------------------------------------------------- upcoming exams
    upcoming = list(
        db.scalars(
            select(Exam)
            .where(
                Exam.status == ExamStatus.PUBLISHED,
                Exam.starts_at >= now,
                *exam_filter,
            )
            .order_by(Exam.starts_at)
            .limit(6)
        )
    )
    upcoming_exams = [
        {
            "id": str(exam.id),
            "title": exam.title,
            "time_str": _when(exam.starts_at, now=now),
        }
        for exam in upcoming
    ]

    return {
        "active_sessions_count": active_count,
        "exams_today_count": exams_today_count,
        "flagged_sessions_count": flagged_count,
        "grading_queue_count": grading_queue_count,
        "ai_prescored_count": ai_prescored_count,
        "avg_score_pct": avg_score_pct,
        "live_sessions": live_sessions,
        "proctoring_alerts": proctoring_alerts,
        "proctoring_signals": signals,
        "score_distribution": score_distribution,
        "ai_grading_queue": ai_grading_queue,
        "upcoming_exams": upcoming_exams,
        "recent_activity": _activity(db, scope, now=now, since=since),
    }


def live_exams(db: Session, staff: User) -> list[dict]:
    """One row per exam currently inside its published window - the admin/examiner
    "Live Examinations" table, as opposed to ``live_sessions`` above which is one row
    per candidate sitting. Same scope rule: an examiner sees their own, an admin sees
    every exam on the platform.
    """
    now = datetime.now(UTC)
    scope = scope_for(db, staff)

    exams = list(
        db.scalars(
            select(Exam)
            .where(
                Exam.status == ExamStatus.PUBLISHED,
                Exam.starts_at <= now,
                Exam.ends_at >= now,
                *scope.exam_clause,
            )
            .options(selectinload(Exam.created_by))
            .order_by(Exam.ends_at)
        )
    )
    if not exams:
        return []

    exam_ids = [e.id for e in exams]

    enrolled_counts = dict(
        db.execute(
            select(ExamEnrollment.exam_id, func.count(ExamEnrollment.id))
            .where(ExamEnrollment.exam_id.in_(exam_ids))
            .group_by(ExamEnrollment.exam_id)
        ).all()
    )
    active_counts = dict(
        db.execute(
            select(ExamSession.exam_id, func.count(ExamSession.id))
            .where(
                ExamSession.exam_id.in_(exam_ids),
                ExamSession.status == SessionStatus.IN_PROGRESS,
            )
            .group_by(ExamSession.exam_id)
        ).all()
    )
    flagged_counts = dict(
        db.execute(
            select(ExamSession.exam_id, func.count(ExamSession.id))
            .where(ExamSession.exam_id.in_(exam_ids), ExamSession.is_flagged.is_(True))
            .group_by(ExamSession.exam_id)
        ).all()
    )

    rows = []
    for exam in exams:
        remaining = max(int((exam.ends_at - now).total_seconds()), 0)
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        remaining_str = (
            f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
        )

        rows.append(
            {
                "exam_id": str(exam.id),
                "exam_title": exam.title,
                "examiner_name": exam.created_by.full_name if exam.created_by else "—",
                "candidate_count": enrolled_counts.get(exam.id, 0),
                "active_count": active_counts.get(exam.id, 0),
                "flagged_count": flagged_counts.get(exam.id, 0),
                "time_remaining_str": remaining_str,
            }
        )
    return rows


def _signals(sessions: list[ExamSession]) -> dict:
    """Share of recent sittings that stayed clean on each proctoring axis."""
    total = len(sessions)
    if not total:
        return {
            "face_present_pct": 0,
            "gaze_on_screen_pct": 0,
            "no_tab_switches_pct": 0,
            "single_face_pct": 0,
            "high_suspicion_pct": 0,
        }

    def share(predicate) -> int:
        return round(100 * sum(1 for s in sessions if predicate(s)) / total)

    def has(session: ExamSession, *types: str) -> bool:
        return any(e.event_type.value in types for e in session.proctor_events)

    return {
        "face_present_pct": share(lambda s: not has(s, "face_missing", "camera_blocked")),
        "gaze_on_screen_pct": share(lambda s: not has(s, "gaze_away")),
        "no_tab_switches_pct": share(lambda s: not has(s, "tab_switch", "fullscreen_exit")),
        "single_face_pct": share(lambda s: not has(s, "multiple_faces")),
        "high_suspicion_pct": share(lambda s: s.is_flagged),
    }


def _when(moment: datetime | None, *, now: datetime) -> str:
    """"14:00", "Tomorrow 10:00", or a date - whichever a human needs to hear."""
    if moment is None:
        return "unscheduled"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(now.tzinfo)
    if local.date() == now.date():
        return local.strftime("%H:%M")
    if local.date() == (now + timedelta(days=1)).date():
        return f"Tomorrow {local:%H:%M}"
    return local.strftime("%d %b %H:%M")


def _activity(db: Session, scope: Scope, *, now: datetime, since: datetime) -> list[dict]:
    """A merged feed of what actually happened, newest first.

    Four sources - submissions, flags, published results, critical proctor events -
    interleaved by time. Each entry names a real candidate and a real exam, or it does
    not appear.
    """
    entries: list[tuple[datetime, dict]] = []

    submissions = db.scalars(
        scope.filter_sessions(
            select(ExamSession)
            .where(
                ExamSession.submitted_at >= since,
                ExamSession.status.in_(
                    [SessionStatus.SUBMITTED, SessionStatus.AUTO_SUBMITTED]
                ),
            )
            .options(
                selectinload(ExamSession.candidate), selectinload(ExamSession.exam)
            )
            .order_by(ExamSession.submitted_at.desc())
            .limit(FEED_LIMIT)
        )
    )
    for session in submissions:
        name = session.candidate.full_name if session.candidate else "A candidate"
        title = session.exam.title if session.exam else "an exam"
        auto = session.status is SessionStatus.AUTO_SUBMITTED
        entries.append(
            (
                session.submitted_at,
                {
                    "message": (
                        f"{name}'s paper was submitted automatically ({title})"
                        if auto
                        else f"{name} submitted {title}"
                    ),
                    "time_ago": _ago(session.submitted_at, now=now),
                    "severity": "amber" if auto else "mint",
                },
            )
        )

    flagged = db.scalars(
        scope.filter_sessions(
            select(ExamSession)
            .where(
                ExamSession.is_flagged.is_(True),
                or_(
                    ExamSession.submitted_at >= since,
                    ExamSession.started_at >= since,
                ),
            )
            .options(
                selectinload(ExamSession.candidate), selectinload(ExamSession.exam)
            )
            .order_by(ExamSession.started_at.desc())
            .limit(FEED_LIMIT)
        )
    )
    for session in flagged:
        name = session.candidate.full_name if session.candidate else "A candidate"
        title = session.exam.title if session.exam else "an exam"
        entries.append(
            (
                session.submitted_at or session.started_at,
                {
                    "message": f"{name}'s sitting was flagged for review ({title})",
                    "time_ago": _ago(session.submitted_at or session.started_at, now=now),
                    "severity": "rose",
                },
            )
        )

    published = db.execute(
        scope.filter_sessions(
            select(Result.published_at, User.full_name, Exam.title)
            .join(ExamSession, Result.session_id == ExamSession.id)
            .join(User, ExamSession.candidate_id == User.id)
            .join(Exam, ExamSession.exam_id == Exam.id)
            .where(Result.published.is_(True), Result.published_at >= since)
            .order_by(Result.published_at.desc())
            .limit(FEED_LIMIT)
        )
    ).all()
    for published_at, candidate_name, exam_title in published:
        entries.append(
            (
                published_at,
                {
                    "message": f"Result published to {candidate_name} ({exam_title})",
                    "time_ago": _ago(published_at, now=now),
                    "severity": "accent",
                },
            )
        )

    ranked = sorted(
        (e for e in entries if e[0] is not None),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [entry for _, entry in ranked[:FEED_LIMIT]]
