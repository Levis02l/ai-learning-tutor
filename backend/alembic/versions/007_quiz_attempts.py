"""add multiple-choice quiz attempts

Revision ID: 007
Revises: 006
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_items",
        sa.Column(
            "options",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "quiz_items",
        sa.Column("correct_option_id", sa.String(), nullable=True),
    )
    op.add_column(
        "quiz_items",
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("quiz_items", "options", server_default=None)
    op.alter_column("quiz_items", "explanation", server_default=None)

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("quiz_item_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_id", sa.String(), nullable=False),
        sa.Column("selected_option_text", sa.Text(), nullable=False),
        sa.Column("correct_option_id", sa.String(), nullable=False),
        sa.Column("correct_option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["quiz_item_id"], ["quiz_items.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_course_id", "quiz_attempts", ["course_id"])
    op.create_index(
        "ix_quiz_attempts_quiz_item_id",
        "quiz_attempts",
        ["quiz_item_id"],
    )
    op.create_index(
        "ix_quiz_attempts_attempted_at",
        "quiz_attempts",
        ["attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_attempted_at", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_quiz_item_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_course_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_column("quiz_items", "explanation")
    op.drop_column("quiz_items", "correct_option_id")
    op.drop_column("quiz_items", "options")
