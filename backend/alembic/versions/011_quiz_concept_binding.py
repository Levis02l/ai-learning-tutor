"""add quiz concept binding

Revision ID: 011
Revises: 010
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("quiz_items", sa.Column("concept_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_quiz_items_concept_id_concepts",
        "quiz_items",
        "concepts",
        ["concept_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_quiz_items_concept_id", "quiz_items", ["concept_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_items_concept_id", table_name="quiz_items")
    op.drop_constraint(
        "fk_quiz_items_concept_id_concepts",
        "quiz_items",
        type_="foreignkey",
    )
    op.drop_column("quiz_items", "concept_id")
