"""add traceability fields to quiz items

Revision ID: 004
Revises: 003
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_items",
        sa.Column("evidence_quote", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "quiz_items",
        sa.Column(
            "question_type",
            sa.String(),
            nullable=False,
            server_default="conceptual",
        ),
    )
    op.add_column(
        "quiz_items",
        sa.Column(
            "traceability_label",
            sa.String(),
            nullable=False,
            server_default="not_traceable",
        ),
    )


def downgrade() -> None:
    op.drop_column("quiz_items", "traceability_label")
    op.drop_column("quiz_items", "question_type")
    op.drop_column("quiz_items", "evidence_quote")
