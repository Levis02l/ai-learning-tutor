"""add policy misconception snapshot

Revision ID: 015
Revises: 014
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policy_decisions",
        sa.Column("misconception_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("policy_decisions", "misconception_snapshot")
