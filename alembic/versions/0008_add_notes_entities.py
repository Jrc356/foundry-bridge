"""Add notes_entities association table

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-23

Creates a many-to-many join table between notes and entities so that each
entity can reference all the notes in which it was mentioned or created.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes_entities",
        sa.Column(
            "note_id",
            sa.BigInteger,
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            sa.BigInteger,
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("notes_entities")
