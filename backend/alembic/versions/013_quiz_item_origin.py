"""add quiz item origin

Revision ID: 013
Revises: 012
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_items",
        sa.Column(
            "origin",
            sa.String(),
            nullable=False,
            server_default="manual_practice",
        ),
    )
    op.create_index("ix_quiz_items_origin", "quiz_items", ["origin"])


def downgrade() -> None:
    op.drop_index("ix_quiz_items_origin", table_name="quiz_items")
    op.drop_column("quiz_items", "origin")
