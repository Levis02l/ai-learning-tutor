"""add socratic sessions

Revision ID: 016
Revises: 015
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "socratic_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("concept_id", sa.Integer(), nullable=True),
        sa.Column("source_policy_decision_id", sa.Integer(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_stage", sa.String(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("max_turns", sa.Integer(), nullable=False),
        sa.Column("learner_state_snapshot", sa.JSON(), nullable=False),
        sa.Column("concept_snapshot", sa.JSON(), nullable=True),
        sa.Column("misconception_snapshot", sa.JSON(), nullable=True),
        sa.Column("evidence_state_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_chunks_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_policy_decision_id"],
            ["policy_decisions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_socratic_sessions_user_id", "socratic_sessions", ["user_id"])
    op.create_index(
        "ix_socratic_sessions_course_id",
        "socratic_sessions",
        ["course_id"],
    )
    op.create_index(
        "ix_socratic_sessions_concept_id",
        "socratic_sessions",
        ["concept_id"],
    )
    op.create_index(
        "ix_socratic_sessions_status",
        "socratic_sessions",
        ["status"],
    )

    op.create_table(
        "socratic_turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("tutor_message", sa.Text(), nullable=False),
        sa.Column("student_response", sa.Text(), nullable=True),
        sa.Column("assessment", sa.String(), nullable=True),
        sa.Column("assessment_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["socratic_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_socratic_turns_session_id", "socratic_turns", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_socratic_turns_session_id", table_name="socratic_turns")
    op.drop_table("socratic_turns")
    op.drop_index("ix_socratic_sessions_status", table_name="socratic_sessions")
    op.drop_index("ix_socratic_sessions_concept_id", table_name="socratic_sessions")
    op.drop_index("ix_socratic_sessions_course_id", table_name="socratic_sessions")
    op.drop_index("ix_socratic_sessions_user_id", table_name="socratic_sessions")
    op.drop_table("socratic_sessions")
