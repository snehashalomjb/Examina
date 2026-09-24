"""Domain enums. These map to native PostgreSQL enum types."""

from __future__ import annotations

import enum

#: UI/content locales the platform can render or store translated text in. A plain
#: tuple + CHECK constraint (see the translation tables) rather than a Postgres ENUM,
#: so adding a language later is a constraint swap, not an ``ALTER TYPE``.
SUPPORTED_LOCALES: tuple[str, ...] = ("en", "te", "hi", "ta", "ml", "kn")
DEFAULT_LOCALE = "en"


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
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    NUMERICAL = "numerical"
    PASSAGE = "passage"
    CODING = "coding"
    SQL = "sql"
    IMAGE_UPLOAD = "image_upload"


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
    QuestionType.SQL,
}

#: Carries no answer of its own. A passage is a container: the candidate reads it and
#: answers its child questions, so it is never scored and never counted in a paper's marks.
CONTAINER_TYPES = {QuestionType.PASSAGE}

#: Every type that is auto-scorable without a grader.
AUTO_SCORED_TYPES = OBJECTIVE_TYPES | RESPONSE_TYPES

#: Types that own rows in ``question_options``.
OPTION_BEARING_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE}

#: Types whose answer is free prose, and therefore word-countable.
TEXT_ANSWER_TYPES = {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER, QuestionType.SQL}


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


class QuestionSource(str, enum.Enum):
    """How a question came to exist.

    Kept as provenance rather than a permission: an imported question is not less
    valid than a typed one, but an examiner browsing the bank wants to know which
    of these an AI wrote, and the spec asks for that shelf explicitly.
    """

    MANUAL = "manual"
    AI_GENERATED = "ai_generated"
    IMPORTED = "imported"


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


class IntegrityVerdict(str, enum.Enum):
    """An examiner's ruling on how a sitting was conducted.

    Proctoring produces signals, not verdicts. A suspicion score and a pile of events
    say "look at this"; only a named examiner decides whether what happened was
    malpractice. That decision is recorded here, separately from the score, because a
    candidate can sit honestly and do badly, or cheat and do well - the two axes are
    independent and conflating them is how an automated system wrongly fails someone.

    ``PENDING`` is the default and means nobody has looked yet. A flagged sitting cannot
    have its result published while it is still ``PENDING``.
    """

    PENDING = "pending"
    #: Reviewed and judged a genuine attempt. The paper is graded and published normally.
    CLEARED = "cleared"
    #: Reviewed and judged malpractice. The result is withheld rather than published.
    MALPRACTICE = "malpractice"


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
    PHONE_DETECTED = "phone_detected"
    GAZE_AWAY = "gaze_away"
    TAB_SWITCH = "tab_switch"
    WINDOW_BLUR = "window_blur"
    FULLSCREEN_EXIT = "fullscreen_exit"
    CAMERA_BLOCKED = "camera_blocked"
    PASTE_ATTEMPT = "paste_attempt"
    COPY_ATTEMPT = "copy_attempt"
    DEVTOOLS_OPEN = "devtools_open"
    RIGHT_CLICK = "right_click"
    CUT_ATTEMPT = "cut_attempt"
    TEXT_SELECTION = "text_selection"
    ADDITIONAL_PERSON = "additional_person"
    MIC_DISCONNECTED = "mic_disconnected"
    NETWORK_LOST = "network_lost"
    #: Never auto-detected - MediaPipe has no headphone class. An examiner raises this
    #: by hand from the review screen; it always carries weight 0 so it can never move
    #: the suspicion score or the auto-submit ladder on its own.
    HEADPHONES_MANUAL = "headphones_manual"


class ProctorSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
