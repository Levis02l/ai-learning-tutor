"""add courses and course scoping

Revision ID: 006
Revises: 005
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"])

    op.add_column("documents", sa.Column("course_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_documents_course_id_courses",
        "documents",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_course_id", "documents", ["course_id"])

    op.add_column("quiz_items", sa.Column("course_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_quiz_items_course_id_courses",
        "quiz_items",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_quiz_items_course_id", "quiz_items", ["course_id"])

    op.add_column("review_records", sa.Column("course_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_review_records_course_id_courses",
        "review_records",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE review_records
        SET course_id = quiz_items.course_id
        FROM quiz_items
        WHERE review_records.item_id = quiz_items.id
        """
    )
    op.create_index("ix_review_records_course_id", "review_records", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_review_records_course_id", table_name="review_records")
    op.drop_constraint(
        "fk_review_records_course_id_courses",
        "review_records",
        type_="foreignkey",
    )
    op.drop_column("review_records", "course_id")

    op.drop_index("ix_quiz_items_course_id", table_name="quiz_items")
    op.drop_constraint(
        "fk_quiz_items_course_id_courses",
        "quiz_items",
        type_="foreignkey",
    )
    op.drop_column("quiz_items", "course_id")

    op.drop_index("ix_documents_course_id", table_name="documents")
    op.drop_constraint(
        "fk_documents_course_id_courses",
        "documents",
        type_="foreignkey",
    )
    op.drop_column("documents", "course_id")

    op.drop_index("ix_courses_user_id", table_name="courses")
    op.drop_table("courses")
