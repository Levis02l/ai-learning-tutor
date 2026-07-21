"""add concept graph

Revision ID: 010
Revises: 009
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "extraction_confidence",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "course_id",
            "normalized_name",
            name="uq_concepts_course_normalized_name",
        ),
    )
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"])

    op.create_table(
        "concept_source_chunks",
        sa.Column("concept_id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), primary_key=True),
        sa.Column(
            "relevance_score",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_concept_source_chunks_chunk_id",
        "concept_source_chunks",
        ["chunk_id"],
    )

    op.create_table(
        "concept_prerequisites",
        sa.Column("concept_id", sa.Integer(), primary_key=True),
        sa.Column("prerequisite_concept_id", sa.Integer(), primary_key=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "concept_id <> prerequisite_concept_id",
            name="ck_concept_prerequisites_not_self",
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prerequisite_concept_id"],
            ["concepts.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_concept_prerequisites_prerequisite_concept_id",
        "concept_prerequisites",
        ["prerequisite_concept_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_prerequisites_prerequisite_concept_id",
        table_name="concept_prerequisites",
    )
    op.drop_table("concept_prerequisites")

    op.drop_index(
        "ix_concept_source_chunks_chunk_id",
        table_name="concept_source_chunks",
    )
    op.drop_table("concept_source_chunks")

    op.drop_index("ix_concepts_course_id", table_name="concepts")
    op.drop_table("concepts")
