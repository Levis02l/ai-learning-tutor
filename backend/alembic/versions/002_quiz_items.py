"""add quiz items table

Revision ID: 002
Revises: 001
Create Date: 2026-06-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=False),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_quiz_items_user_id", "quiz_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_items_user_id", table_name="quiz_items")
    op.drop_table("quiz_items")
