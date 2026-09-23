"""pin pool questions to a section

Revision ID: 05483046fcc2
Revises: 2e4b54596555
Create Date: 2026-09-13 16:49:11.426022
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '05483046fcc2'
down_revision: str | None = '2e4b54596555'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Let an examiner choose questions *for* a section, not just for the exam.

    Nullable by design: every existing row becomes "available to any section", which is
    exactly how the pool behaved before this column existed. ON DELETE SET NULL so
    removing a section returns its questions to the shared pool instead of taking
    authored questions down with it.
    """
    op.add_column(
        "exam_questions",
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_exam_questions_section_id", "exam_questions", ["section_id"], unique=False
    )
    op.create_foreign_key(
        "fk_exam_questions_section_id",
        "exam_questions",
        "exam_sections",
        ["section_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_exam_questions_section_id", "exam_questions", type_="foreignkey")
    op.drop_index("ix_exam_questions_section_id", table_name="exam_questions")
    op.drop_column("exam_questions", "section_id")
