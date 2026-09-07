"""Domain enums. These map to native PostgreSQL enum types."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EXAMINER = "examiner"
    CANDIDATE = "candidate"


class AccessStatus(str, enum.Enum):
    """Admin-controlled gate.

    Examiners register as ``PENDING`` and cannot touch the question bank or any exam
    until an admin flips them to ``APPROVED``. Candidates are approved on registration.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


class LoginAccessStatus(str, enum.Enum):
    """Permission to *use* the platform - deliberately separate from account state.

    A candidate's account is created active and stays active; this is the gate that an
    administrator (or an authorised examiner) opens. Revoking access sets an approved
    request back to ``REJECTED`` with a review note, so there is exactly one axis to
    reason about when deciding whether someone may log in.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    IMAGE_UPLOAD = "image_upload"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    NUMERICAL = "numerical"
    PASSAGE = "passage"
    CODING = "coding"


#: Scored by comparing selected option ids against the key. No human needed.
OBJECTIVE_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE}

#: Scored by comparing a typed response against ``spec``. Also machine-scored, but the
#: comparison is textual or numeric rather than a set of option ids, so it is its own
#: family - see ``app.services.auto_evaluator``.
RESPONSE_TYPES = {QuestionType.FILL_BLANK, QuestionType.NUMERICAL}

#: Needs a grader (model or human) to read the answer.
SUBJECTIVE_TYPES = {
    QuestionType.SHORT_ANSWER,
    QuestionType.LONG_ANSWER,
    QuestionType.IMAGE_UPLOAD,
    QuestionType.CODING,
}

#: Carries no answer of its own. A passage is a container: the candidate reads it and
#: answers its child questions, so it is never scored and never counted in a paper's marks.
CONTAINER_TYPES = {QuestionType.PASSAGE}

#: Every type that is auto-scorable without a grader.
AUTO_SCORED_TYPES = OBJECTIVE_TYPES | RESPONSE_TYPES

#: Types that own rows in ``question_options``.
OPTION_BEARING_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE}

#: Types whose answer is free prose, and therefore word-countable.
TEXT_ANSWER_TYPES = {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}


class ExamType(str, enum.Enum):
    """Which of the two modes an exam runs in.

    Both modes share one engine, one question bank and one session lifecycle. The type
    decides which configuration fields apply and which reports are offered - not how the
    exam is delivered.
    """

    ACADEMIC = "academic"
    CORPORATE = "corporate"


class QuestionCategory(str, enum.Enum):
    """The bank's top-level shelf. Orthogonal to ``subject``.

    A Python question is category ``technical``, subject ``Python``; a percentages
    question is category ``aptitude``, subject ``Quantitative Aptitude``. Corporate
    section rules select on category; academic exams mostly select on subject.
    """

    ACADEMIC = "academic"
    APTITUDE = "aptitude"
    VERBAL_ABILITY = "verbal_ability"
    LOGICAL_REASONING = "logical_reasoning"
    TECHNICAL = "technical"
    CODING = "coding"


class QuestionStatus(str, enum.Enum):
    """Authoring lifecycle. Only ``published`` questions may enter an exam pool."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DraftStatus(str, enum.Enum):
    """Review state of an AI-generated question draft.

    A draft is never a question. It becomes one only when an examiner approves it, which
    is what keeps generated content out of a live paper without a human decision.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ShortlistStatus(str, enum.Enum):
    """An examiner's recruitment decision. The platform never sets this on its own."""

    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    TERMINATED = "terminated"


class GradeStatus(str, enum.Enum):
    UNANSWERED = "unanswered"
    AUTO_SCORED = "auto_scored"
    PENDING_AI = "pending_ai"
    AI_SCORED = "ai_scored"
    EXAMINER_REVIEWED = "examiner_reviewed"


class ProctorEventType(str, enum.Enum):
    FACE_MISSING = "face_missing"
    MULTIPLE_FACES = "multiple_faces"
    GAZE_AWAY = "gaze_away"
    TAB_SWITCH = "tab_switch"
    WINDOW_BLUR = "window_blur"
    FULLSCREEN_EXIT = "fullscreen_exit"
    CAMERA_BLOCKED = "camera_blocked"
    PASTE_ATTEMPT = "paste_attempt"
    COPY_ATTEMPT = "copy_attempt"
    DEVTOOLS_OPEN = "devtools_open"


class ProctorSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
