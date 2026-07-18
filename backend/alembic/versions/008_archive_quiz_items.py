"""archive quiz items

Revision ID: 008
Revises: 007
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_items",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_quiz_items_archived_at", "quiz_items", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_quiz_items_archived_at", table_name="quiz_items")
    op.drop_column("quiz_items", "archived_at")
