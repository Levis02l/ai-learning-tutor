"""add socratic completion check links

Revision ID: 017
Revises: 016
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "socratic_sessions",
        sa.Column("completion_quiz_item_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "socratic_sessions",
        sa.Column("completion_quiz_attempt_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_socratic_sessions_completion_quiz_item_id_quiz_items",
        "socratic_sessions",
        "quiz_items",
        ["completion_quiz_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_socratic_sessions_completion_quiz_attempt_id_quiz_attempts",
        "socratic_sessions",
        "quiz_attempts",
        ["completion_quiz_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_socratic_sessions_completion_quiz_attempt_id_quiz_attempts",
        "socratic_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_socratic_sessions_completion_quiz_item_id_quiz_items",
        "socratic_sessions",
        type_="foreignkey",
    )
    op.drop_column("socratic_sessions", "completion_quiz_attempt_id")
    op.drop_column("socratic_sessions", "completion_quiz_item_id")
