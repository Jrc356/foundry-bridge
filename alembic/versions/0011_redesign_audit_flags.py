"""Redesign audit_flags taxonomy columns

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM audit_flags")

    op.drop_column("audit_flags", "flag_type")
    op.drop_column("audit_flags", "target_type")

    op.add_column("audit_flags", sa.Column("operation", sa.String(10), nullable=False))
    op.add_column("audit_flags", sa.Column("table_name", sa.String(30), nullable=False))
    op.add_column("audit_flags", sa.Column("confidence", sa.String(10), nullable=False))

    op.create_check_constraint(
        "ck_audit_flags_operation",
        "audit_flags",
        "operation IN ('create', 'update', 'delete', 'merge')",
    )
    op.create_check_constraint(
        "ck_audit_flags_table_name",
        "audit_flags",
        "table_name IN ('entities', 'quests', 'threads', 'events', 'decisions', 'loot', 'important_quotes', 'combat_updates')",
    )
    op.create_check_constraint(
        "ck_audit_flags_confidence",
        "audit_flags",
        "confidence IN ('low', 'medium', 'high')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM audit_flags")

    op.drop_constraint("ck_audit_flags_confidence", "audit_flags", type_="check")
    op.drop_constraint("ck_audit_flags_table_name", "audit_flags", type_="check")
    op.drop_constraint("ck_audit_flags_operation", "audit_flags", type_="check")

    op.drop_column("audit_flags", "confidence")
    op.drop_column("audit_flags", "table_name")
    op.drop_column("audit_flags", "operation")

    op.add_column("audit_flags", sa.Column("flag_type", sa.String(50), nullable=False))
    op.add_column("audit_flags", sa.Column("target_type", sa.String(20), nullable=True))
