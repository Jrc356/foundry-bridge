"""Add quest_description_history table

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-23

Captures a snapshot of each quest's description before the note taker
overwrites it, so the full evolution of a quest can be reviewed over time.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quest_description_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "quest_id",
            sa.BigInteger,
            sa.ForeignKey("quests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=False),
        # note_id is informational only — intentionally NOT a FK so that
        # deleting a note does not cascade-delete historical descriptions.
        sa.Column("note_id", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_quest_description_history_quest_id",
        "quest_description_history",
        ["quest_id"],
    )


def downgrade() -> None:
    op.drop_table("quest_description_history")
