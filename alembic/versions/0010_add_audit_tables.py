"""Add audit tables and soft-delete foundation

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-25

Introduces audit_runs and audit_flags for the auditing agent pipeline,
adds note audit marker support, and adds soft-delete fields to quests and threads.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("games.id"), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("trigger_source", sa.String(20), nullable=False),
        sa.Column(
            "notes_audited",
            postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("notes_audited_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_note_id", sa.BigInteger, nullable=True),
        sa.Column("max_note_id", sa.BigInteger, nullable=True),
        sa.Column("audit_note_id", sa.BigInteger, sa.ForeignKey("notes.id"), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_audit_runs_status",
        ),
        sa.CheckConstraint(
            "trigger_source IN ('auto', 'manual')",
            name="ck_audit_runs_trigger_source",
        ),
    )

    op.create_index("ix_audit_runs_game_id", "audit_runs", ["game_id"])
    op.create_index("ix_audit_runs_status", "audit_runs", ["status"])
    op.create_index(
        "uq_audit_runs_game_one_running",
        "audit_runs",
        ["game_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "audit_flags",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("games.id"), nullable=False),
        sa.Column(
            "audit_run_id",
            sa.BigInteger,
            sa.ForeignKey("audit_runs.id"),
            nullable=False,
        ),
        sa.Column("flag_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=True),
        sa.Column("target_id", sa.BigInteger, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("suggested_change", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="ck_audit_flags_status",
        ),
    )

    op.create_index(
        "ix_audit_flags_game_id_status",
        "audit_flags",
        ["game_id", "status"],
    )
    op.create_index("ix_audit_flags_audit_run_id", "audit_flags", ["audit_run_id"])

    op.add_column(
        "notes",
        sa.Column("is_audit", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "quests",
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("quests", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quests", sa.Column("deleted_reason", sa.Text, nullable=True))

    op.add_column(
        "threads",
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("threads", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("threads", sa.Column("deleted_reason", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("threads", "deleted_reason")
    op.drop_column("threads", "deleted_at")
    op.drop_column("threads", "is_deleted")

    op.drop_column("quests", "deleted_reason")
    op.drop_column("quests", "deleted_at")
    op.drop_column("quests", "is_deleted")

    op.drop_column("notes", "is_audit")

    op.drop_index("ix_audit_flags_audit_run_id", table_name="audit_flags")
    op.drop_index("ix_audit_flags_game_id_status", table_name="audit_flags")
    op.drop_table("audit_flags")

    op.drop_index("uq_audit_runs_game_one_running", table_name="audit_runs")
    op.drop_index("ix_audit_runs_status", table_name="audit_runs")
    op.drop_index("ix_audit_runs_game_id", table_name="audit_runs")
    op.drop_table("audit_runs")
