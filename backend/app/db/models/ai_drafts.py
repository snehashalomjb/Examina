"""AI-generated question drafts awaiting examiner review.

A draft is deliberately *not* a question. It lives in its own table with its own status,
and the only way its content reaches the bank is an examiner pressing approve, which
creates a real ``Question`` row and links it back here. There is no code path that
publishes generated content on its own - the separation is the safeguard, not a policy
written in a comment somewhere.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import Difficulty, DraftStatus, QuestionCategory, QuestionType

if TYPE_CHECKING:
    from app.db.models.question import Question, Subject
    from app.db.models.user import User


class AiQuestionDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One generated question, pending a human decision.

    ``payload`` holds the whole proposed question - body, options, answer key,
    explanation - in the same shape the question-creation API accepts, so approving is a
    validated create rather than a second parser. The examiner may edit the payload
    before approving; the edited version is what gets saved, and the original stays in
    ``original_payload`` so a reviewer can see what the model actually produced.
    """

    __tablename__ = "ai_question_drafts"

    #: What was asked for. Kept alongside the result so a batch can be reviewed in
    #: context and a bad prompt is visible as a bad prompt.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL")
    )
    category: Mapped[QuestionCategory] = mapped_column(
        Enum(
            QuestionCategory,
            name="question_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    topic: Mapped[str | None] = mapped_column(String(120))
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, name="difficulty", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    #: The proposed question, editable by the reviewing examiner before approval.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    #: What the model first returned, never modified. The audit trail for an edit.
    original_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    #: A generation that failed still gets a row, so a half-empty batch is explainable.
    error: Mapped[str | None] = mapped_column(Text)

    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status", values_callable=lambda e: [m.value for m in e]),
        default=DraftStatus.PENDING,
        server_default=DraftStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)

    #: Set on approval. RESTRICT: the resulting question cannot be hard-deleted while the
    #: draft still points at it, which keeps the provenance of a generated question intact.
    published_question_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT")
    )

    subject: Mapped[Subject | None] = relationship()
    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    published_question: Mapped[Question | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AiQuestionDraft {self.status.value} {self.question_type.value}>"
