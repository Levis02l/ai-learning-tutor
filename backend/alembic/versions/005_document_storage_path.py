"""add document storage path

Revision ID: 005
Revises: 004
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("storage_path", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "storage_path")
