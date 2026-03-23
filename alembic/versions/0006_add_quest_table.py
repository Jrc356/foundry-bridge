"""Add quest table and quest_id FKs on threads and loot

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-23

Quests become a first-class data item separate from the generic entities table.
Threads and loot gain an optional quest_id FK for grouping under a quest.
Existing entity rows with entity_type='quest' are left untouched.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

VECTOR_DIM = 768


def upgrade() -> None:
    # 1. Create quests table
    op.create_table(
        "quests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("games.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "quest_giver_entity_id",
            sa.BigInteger,
            sa.ForeignKey("entities.id"),
            nullable=True,
        ),
        sa.Column(
            "note_ids",
            sa.ARRAY(sa.BigInteger),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder; real type added below
    )

    # Replace the placeholder text column with the proper vector type
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE quests DROP COLUMN embedding"))
    bind.execute(
        sa.text(f"ALTER TABLE quests ADD COLUMN embedding vector({VECTOR_DIM})")
    )

    # 2. Unique constraint on (game_id, name)
    op.create_unique_constraint("uq_quests_game_name", "quests", ["game_id", "name"])

    # 3. Tighten status to only valid values
    op.create_check_constraint(
        "ck_quests_status",
        "quests",
        "status IN ('active', 'completed')",
    )

    # 4. HNSW index for future quests embeddings
    bind.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS quests_embedding_hnsw_idx "
        "ON quests USING hnsw (embedding vector_cosine_ops) "
        "WITH (m=16, ef_construction=64)"
    ))

    # 5. Add quest_id FK to threads
    op.add_column(
        "threads",
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), nullable=True),
    )

    # 6. Add quest_id FK to loot
    op.add_column(
        "loot",
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("loot", "quest_id")
    op.drop_column("threads", "quest_id")
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS quests_embedding_hnsw_idx"))
    op.drop_table("quests")
