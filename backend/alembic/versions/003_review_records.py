"""add review records table

Revision ID: 003
Revises: 002
Create Date: 2026-06-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("quiz_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("stability", sa.Float(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_review_records_user_id", "review_records", ["user_id"])
    op.create_index("ix_review_records_item_id", "review_records", ["item_id"])
    op.create_index("ix_review_records_due_at", "review_records", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_review_records_due_at", table_name="review_records")
    op.drop_index("ix_review_records_item_id", table_name="review_records")
    op.drop_index("ix_review_records_user_id", table_name="review_records")
    op.drop_table("review_records")
