"""question bank: categories, topics, status, images, spec, passage children

Adds the five new question types as enum values and the bank columns the two exam
modes need. Deliberately split from the exam-side revision that follows it: Postgres
allows ``ALTER TYPE ... ADD VALUE`` inside a transaction, but the added value cannot be
*used* until that transaction commits, and the seed data / defaults in the next revision
reference the new types.

Every column added here is nullable or carries a default chosen to preserve existing
behaviour exactly:
  - ``category`` defaults to 'academic' - what every pre-existing question effectively is
  - ``status`` defaults to 'published' - a 'draft' default would silently empty the pool
    of every exam built before this column existed

Revision ID: b2e91f4a7c33
Revises: a17b4c9de204
Create Date: 2026-09-03 12:31:07.442918
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b2e91f4a7c33'
down_revision: str | None = 'a17b4c9de204'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_QUESTION_TYPES = ("true_false", "fill_blank", "numerical", "passage", "coding")


def upgrade() -> None:
    # --- widen question_type ------------------------------------------------
    # IF NOT EXISTS keeps the migration re-runnable against a partially upgraded
    # database; enum values cannot be removed, so the downgrade leaves these in place.
    for value in NEW_QUESTION_TYPES:
        op.execute(f"ALTER TYPE question_type ADD VALUE IF NOT EXISTS '{value}'")

    # --- new enum types -----------------------------------------------------
    sa.Enum(
        "academic",
        "aptitude",
        "verbal_ability",
        "logical_reasoning",
        "technical",
        "coding",
        name="question_category",
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum("draft", "published", "archived", name="question_status").create(
        op.get_bind(), checkfirst=True
    )

    # Reference the types by name from here on. A bare sa.Enum() inside add_column emits
    # its own unconditional CREATE TYPE, which collides with the explicit create above.
    question_category = postgresql.ENUM(name="question_category", create_type=False)
    question_status = postgresql.ENUM(name="question_status", create_type=False)

    # --- questions ----------------------------------------------------------
    op.add_column(
        "questions",
        sa.Column(
            "category",
            question_category,
            nullable=False,
            server_default="academic",
        ),
    )
    op.add_column("questions", sa.Column("topic", sa.String(length=120), nullable=True))
    op.add_column(
        "questions",
        sa.Column(
            "status",
            question_status,
            nullable=False,
            server_default="published",
        ),
    )
    op.add_column("questions", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("image_key", sa.String(length=512), nullable=True))
    op.add_column("questions", sa.Column("spec", postgresql.JSONB(), nullable=True))
    op.add_column("questions", sa.Column("parent_question_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_questions_parent_question_id_questions",
        "questions",
        "questions",
        ["parent_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_questions_parent_question_id", "questions", ["parent_question_id"]
    )
    op.create_index(
        "ix_questions_bank_filter", "questions", ["category", "topic", "status"]
    )

    # --- question_options ---------------------------------------------------
    op.add_column(
        "question_options", sa.Column("image_key", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("question_options", "image_key")

    op.drop_index("ix_questions_bank_filter", table_name="questions")
    op.drop_index("ix_questions_parent_question_id", table_name="questions")
    op.drop_constraint(
        "fk_questions_parent_question_id_questions", "questions", type_="foreignkey"
    )
    op.drop_column("questions", "parent_question_id")
    op.drop_column("questions", "spec")
    op.drop_column("questions", "image_key")
    op.drop_column("questions", "explanation")
    op.drop_column("questions", "status")
    op.drop_column("questions", "topic")
    op.drop_column("questions", "category")

    sa.Enum(name="question_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="question_category").drop(op.get_bind(), checkfirst=True)

    # The five question_type values stay: Postgres cannot remove an enum value, and any
    # question already authored with one would be orphaned by a forced rewrite.
