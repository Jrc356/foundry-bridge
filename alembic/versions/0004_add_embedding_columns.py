"""Add embedding columns to all searchable tables

Revision ID: 0004
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0004"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

VECTOR_DIM = 768
SEARCHABLE_TABLES = (
    "entities",
    "threads",
    "events",
    "notes",
    "decisions",
    "loot",
    "combat_updates",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for table in SEARCHABLE_TABLES:
        op.add_column(table, sa.Column("embedding", Vector(VECTOR_DIM), nullable=True))
    # No HNSW indexes yet — only useful once data is present.
    # No backfill yet — handled in 0005.


def downgrade() -> None:
    for table in SEARCHABLE_TABLES:
        op.drop_column(table, "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
