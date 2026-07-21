"""add concept-aware policy snapshots

Revision ID: 012
Revises: 011
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policy_decisions",
        sa.Column(
            "learner_state_scope",
            sa.String(),
            nullable=False,
            server_default="course",
        ),
    )
    op.add_column(
        "policy_decisions",
        sa.Column("concept_state_snapshot", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_policy_decisions_learner_state_scope",
        "policy_decisions",
        ["learner_state_scope"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_policy_decisions_learner_state_scope",
        table_name="policy_decisions",
    )
    op.drop_column("policy_decisions", "concept_state_snapshot")
    op.drop_column("policy_decisions", "learner_state_scope")
