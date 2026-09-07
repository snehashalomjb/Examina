"""exam modes, sections, attempts, recruitment and AI drafts

The exam-side half of the two-mode change. Split from b2e91f4a7c33 because the enum
values that revision adds cannot be referenced until its transaction has committed.

Backward compatibility is the whole design here:
  - exam_type defaults to 'academic', so every existing exam keeps its behaviour
  - max_attempts defaults to 1, which is exactly what the old two-column unique
    constraint enforced, so widening that constraint changes nothing in practice
  - exam_sections starts empty; the paper generator synthesises a single implicit
    section from exams.selection_rules when an exam has no rows here
  - answers.section_id is nullable and SET NULL - deleting a section must never
    delete a candidate's submitted work

Revision ID: c4d07b8e1a92
Revises: b2e91f4a7c33
Create Date: 2026-09-03 12:34:52.118203
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'c4d07b8e1a92'
down_revision: str | None = 'b2e91f4a7c33'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sa.Enum("academic", "corporate", name="exam_type").create(op.get_bind(), checkfirst=True)
    sa.Enum("pending", "approved", "rejected", name="draft_status").create(
        op.get_bind(), checkfirst=True
    )
    sa.Enum("shortlisted", "rejected", "on_hold", name="shortlist_status").create(
        op.get_bind(), checkfirst=True
    )

    # Reference the types by name from here on. A bare sa.Enum() inside add_column or
    # create_table emits its own unconditional CREATE TYPE, which collides with the
    # explicit create above - and with itself, when one type is used by two tables.
    exam_type = postgresql.ENUM(name="exam_type", create_type=False)
    draft_status = postgresql.ENUM(name="draft_status", create_type=False)
    shortlist_status = postgresql.ENUM(name="shortlist_status", create_type=False)

    # ------------------------------------------------------------------ exams
    op.add_column(
        "exams",
        sa.Column("exam_type", exam_type, nullable=False, server_default="academic"),
    )
    op.create_index("ix_exams_exam_type", "exams", ["exam_type"])

    op.add_column("exams", sa.Column("instructions", sa.Text(), nullable=True))
    op.add_column("exams", sa.Column("course", sa.String(length=150), nullable=True))
    op.add_column("exams", sa.Column("department", sa.String(length=150), nullable=True))
    op.add_column("exams", sa.Column("semester", sa.String(length=40), nullable=True))
    op.add_column("exams", sa.Column("company_name", sa.String(length=200), nullable=True))
    op.add_column("exams", sa.Column("job_role", sa.String(length=200), nullable=True))
    op.add_column("exams", sa.Column("declared_total_marks", sa.Float(), nullable=True))
    op.add_column("exams", sa.Column("passing_percentage", sa.Float(), nullable=True))
    op.add_column(
        "exams",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
    )

    # ---------------------------------------------------------- exam_sections
    op.create_table(
        "exam_sections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("selection_rules", postgresql.JSONB(), nullable=False),
        sa.Column("marks_per_question", sa.Float(), nullable=True),
        sa.Column("negative_marks", sa.Float(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name="fk_exam_sections_exam_id_exams", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exam_sections"),
        sa.UniqueConstraint("exam_id", "order_index", name="uq_exam_section_order"),
        sa.UniqueConstraint("exam_id", "name", name="uq_exam_section_name"),
    )
    op.create_index("ix_exam_sections_exam_id", "exam_sections", ["exam_id"])

    # ---------------------------------------------------------------- attempts
    op.add_column(
        "exam_sessions",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
    )
    # Widen, do not remove: the replacement is a strict superset of the old rule.
    op.drop_constraint("uq_exam_session_attempt", "exam_sessions", type_="unique")
    op.create_unique_constraint(
        "uq_exam_session_attempt",
        "exam_sessions",
        ["exam_id", "candidate_id", "attempt_number"],
    )

    # ----------------------------------------------------------------- answers
    op.add_column("answers", sa.Column("section_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_answers_section_id_exam_sections",
        "answers",
        "exam_sections",
        ["section_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_answers_section_id", "answers", ["section_id"])

    # --------------------------------------------------------------- templates
    op.create_table(
        "exam_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("exam_type", exam_type, nullable=False, server_default="corporate"),
        sa.Column("job_role", sa.String(length=200), nullable=True),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_exam_templates_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exam_templates"),
        sa.UniqueConstraint("name", name="uq_exam_template_name"),
    )

    # -------------------------------------------------------------- shortlists
    op.create_table(
        "candidate_shortlists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("status", shortlist_status, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_by_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name="fk_candidate_shortlists_exam_id_exams",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name="fk_candidate_shortlists_candidate_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name="fk_candidate_shortlists_decided_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_shortlists"),
        sa.UniqueConstraint("exam_id", "candidate_id", name="uq_shortlist_per_candidate"),
    )
    op.create_index("ix_candidate_shortlists_exam_id", "candidate_shortlists", ["exam_id"])
    op.create_index(
        "ix_candidate_shortlists_candidate_id", "candidate_shortlists", ["candidate_id"]
    )
    op.create_index("ix_candidate_shortlists_status", "candidate_shortlists", ["status"])

    # --------------------------------------------------------------- ai drafts
    op.create_table(
        "ai_question_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(name="question_category", create_type=False),
            nullable=False,
        ),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column(
            "difficulty", postgresql.ENUM(name="difficulty", create_type=False), nullable=False
        ),
        sa.Column(
            "question_type",
            postgresql.ENUM(name="question_type", create_type=False),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("original_payload", postgresql.JSONB(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("status", draft_status, nullable=False, server_default="pending"),
        sa.Column("requested_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("published_question_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_ai_question_drafts_subject_id_subjects",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name="fk_ai_question_drafts_requested_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name="fk_ai_question_drafts_reviewed_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_question_id"],
            ["questions.id"],
            name="fk_ai_question_drafts_published_question_id_questions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_question_drafts"),
    )
    op.create_index("ix_ai_question_drafts_status", "ai_question_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_question_drafts_status", table_name="ai_question_drafts")
    op.drop_table("ai_question_drafts")

    op.drop_index("ix_candidate_shortlists_status", table_name="candidate_shortlists")
    op.drop_index("ix_candidate_shortlists_candidate_id", table_name="candidate_shortlists")
    op.drop_index("ix_candidate_shortlists_exam_id", table_name="candidate_shortlists")
    op.drop_table("candidate_shortlists")

    op.drop_table("exam_templates")

    op.drop_index("ix_answers_section_id", table_name="answers")
    op.drop_constraint("fk_answers_section_id_exam_sections", "answers", type_="foreignkey")
    op.drop_column("answers", "section_id")

    op.drop_constraint("uq_exam_session_attempt", "exam_sessions", type_="unique")
    op.create_unique_constraint(
        "uq_exam_session_attempt", "exam_sessions", ["exam_id", "candidate_id"]
    )
    op.drop_column("exam_sessions", "attempt_number")

    op.drop_index("ix_exam_sections_exam_id", table_name="exam_sections")
    op.drop_table("exam_sections")

    op.drop_column("exams", "max_attempts")
    op.drop_column("exams", "passing_percentage")
    op.drop_column("exams", "declared_total_marks")
    op.drop_column("exams", "job_role")
    op.drop_column("exams", "company_name")
    op.drop_column("exams", "semester")
    op.drop_column("exams", "department")
    op.drop_column("exams", "course")
    op.drop_column("exams", "instructions")
    op.drop_index("ix_exams_exam_type", table_name="exams")
    op.drop_column("exams", "exam_type")

    sa.Enum(name="shortlist_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="draft_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="exam_type").drop(op.get_bind(), checkfirst=True)
