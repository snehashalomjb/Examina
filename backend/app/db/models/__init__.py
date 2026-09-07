"""Model package. Importing this registers every table on ``Base.metadata``."""

from app.db.base import Base
from app.db.models.ai_drafts import AiQuestionDraft
from app.db.models.enrollment import ExamEnrollment
from app.db.models.enums import (
    AUTO_SCORED_TYPES,
    CONTAINER_TYPES,
    OBJECTIVE_TYPES,
    OPTION_BEARING_TYPES,
    RESPONSE_TYPES,
    SUBJECTIVE_TYPES,
    TEXT_ANSWER_TYPES,
    AccessStatus,
    Difficulty,
    DraftStatus,
    ExamStatus,
    ExamType,
    GradeStatus,
    LoginAccessStatus,
    ProctorEventType,
    ProctorSeverity,
    QuestionCategory,
    QuestionStatus,
    QuestionType,
    SessionStatus,
    ShortlistStatus,
    UserRole,
)
from app.db.models.exam import (
    DEFAULT_GRADING_CONFIG,
    DEFAULT_PROCTOR_CONFIG,
    Exam,
    ExamQuestion,
    ExamSection,
)
from app.db.models.exam_session import Answer, ExamSession
from app.db.models.grading import AiEvaluation, Result
from app.db.models.login_access import LoginAccessRequest
from app.db.models.proctor import ProctorEvent
from app.db.models.question import Question, QuestionOption, Subject
from app.db.models.recruitment import CandidateShortlist, ExamTemplate
from app.db.models.user import User

__all__ = [
    "AUTO_SCORED_TYPES",
    "CONTAINER_TYPES",
    "DEFAULT_GRADING_CONFIG",
    "DEFAULT_PROCTOR_CONFIG",
    "OBJECTIVE_TYPES",
    "OPTION_BEARING_TYPES",
    "RESPONSE_TYPES",
    "SUBJECTIVE_TYPES",
    "TEXT_ANSWER_TYPES",
    "AccessStatus",
    "AiEvaluation",
    "AiQuestionDraft",
    "Answer",
    "Base",
    "CandidateShortlist",
    "Difficulty",
    "DraftStatus",
    "Exam",
    "ExamEnrollment",
    "ExamQuestion",
    "ExamSection",
    "ExamSession",
    "ExamStatus",
    "ExamTemplate",
    "ExamType",
    "GradeStatus",
    "LoginAccessRequest",
    "LoginAccessStatus",
    "ProctorEvent",
    "ProctorEventType",
    "ProctorSeverity",
    "Question",
    "QuestionCategory",
    "QuestionOption",
    "QuestionStatus",
    "QuestionType",
    "Result",
    "SessionStatus",
    "ShortlistStatus",
    "Subject",
    "User",
    "UserRole",
]
