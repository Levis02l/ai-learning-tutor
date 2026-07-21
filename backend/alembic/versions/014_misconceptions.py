"""add misconceptions

Revision ID: 014
Revises: 013
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "misconceptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("quiz_attempt_id", sa.Integer(), nullable=False),
        sa.Column("misconception_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["quiz_attempt_id"],
            ["quiz_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quiz_attempt_id",
            name="uq_misconceptions_quiz_attempt_id",
        ),
    )
    op.create_index("ix_misconceptions_user_id", "misconceptions", ["user_id"])
    op.create_index("ix_misconceptions_course_id", "misconceptions", ["course_id"])
    op.create_index("ix_misconceptions_concept_id", "misconceptions", ["concept_id"])
    op.create_index(
        "ix_misconceptions_quiz_attempt_id",
        "misconceptions",
        ["quiz_attempt_id"],
    )
    op.create_index(
        "ix_misconceptions_misconception_type",
        "misconceptions",
        ["misconception_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_misconceptions_misconception_type", table_name="misconceptions")
    op.drop_index("ix_misconceptions_quiz_attempt_id", table_name="misconceptions")
    op.drop_index("ix_misconceptions_concept_id", table_name="misconceptions")
    op.drop_index("ix_misconceptions_course_id", table_name="misconceptions")
    op.drop_index("ix_misconceptions_user_id", table_name="misconceptions")
    op.drop_table("misconceptions")
