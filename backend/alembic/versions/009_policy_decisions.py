"""add policy decisions

Revision ID: 009
Revises: 008
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("detected_intent", sa.String(), nullable=False),
        sa.Column("learner_state_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_state_snapshot", sa.JSON(), nullable=False),
        sa.Column("selected_action", sa.String(), nullable=False),
        sa.Column("response_strategy", sa.String(), nullable=False),
        sa.Column("primary_reason", sa.String(), nullable=False),
        sa.Column("teaching_reason", sa.Text(), nullable=False),
        sa.Column("suggested_next_step", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("outcome", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_policy_decisions_user_id", "policy_decisions", ["user_id"])
    op.create_index("ix_policy_decisions_course_id", "policy_decisions", ["course_id"])
    op.create_index(
        "ix_policy_decisions_policy_version",
        "policy_decisions",
        ["policy_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_decisions_policy_version", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_course_id", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_user_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")
