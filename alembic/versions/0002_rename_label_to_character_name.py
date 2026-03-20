"""rename label to character_name

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-20

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("transcripts", "label", new_column_name="character_name")


def downgrade() -> None:
    op.alter_column("transcripts", "character_name", new_column_name="label")
