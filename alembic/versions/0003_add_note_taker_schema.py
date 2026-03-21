"""add note taker schema

Revision ID: a1b2c3d4e5f6
Revises: 0002
Create Date: 2026-03-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── games ──────────────────────────────────────────────────────────────────
    op.create_table(
        "games",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("world_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("hostname", "world_id", name="uq_games_hostname_world_id"),
    )

    # ── transcripts: add game_id + note_taker_processed ────────────────────────
    op.add_column(
        "transcripts",
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "transcripts",
        sa.Column(
            "note_taker_processed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index("ix_transcripts_game_id", "transcripts", ["game_id"])
    op.create_index(
        "ix_transcripts_game_id_created_at",
        "transcripts",
        ["game_id", "created_at"],
    )
    # Renaming transcripts.transcript -> transcripts.text
    op.alter_column("transcripts", "transcript", new_column_name="text")

    # ── notes ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "source_transcript_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notes_game_id", "notes", ["game_id"])

    # ── events ─────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("game_id", "text", name="uq_events_game_text"),
    )
    op.create_index("ix_events_game_id", "events", ["game_id"])

    # ── notes_events (many-to-many join) ───────────────────────────────────────
    op.create_table(
        "notes_events",
        sa.Column(
            "note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.BigInteger(),
            sa.ForeignKey("events.id"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("note_id", "event_id"),
    )

    # ── decisions ─────────────────────────────────────────────────────────────
    op.create_table(
        "decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column(
            "note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("made_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_decisions_game_id", "decisions", ["game_id"])
    op.create_index("ix_decisions_note_id", "decisions", ["note_id"])

    # ── loot ──────────────────────────────────────────────────────────────────
    op.create_table(
        "loot",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("acquired_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "game_id", "item_name", "acquired_by",
            name="uq_loot_game_item_acquirer",
        ),
    )
    op.create_index("ix_loot_game_id", "loot", ["game_id"])

    # ── notes_loot (many-to-many join) ────────────────────────────────────────
    op.create_table(
        "notes_loot",
        sa.Column(
            "note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=False,
        ),
        sa.Column(
            "loot_id",
            sa.BigInteger(),
            sa.ForeignKey("loot.id"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("note_id", "loot_id"),
    )

    # ── combat_updates ────────────────────────────────────────────────────────
    op.create_table(
        "combat_updates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column(
            "note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=False,
        ),
        sa.Column("encounter", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_combat_updates_game_id", "combat_updates", ["game_id"])
    op.create_index("ix_combat_updates_note_id", "combat_updates", ["note_id"])

    # ── important_quotes ──────────────────────────────────────────────────────
    op.create_table(
        "important_quotes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column(
            "note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=False,
        ),
        sa.Column(
            "transcript_id",
            sa.BigInteger(),
            sa.ForeignKey("transcripts.id"),
            nullable=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_important_quotes_game_id", "important_quotes", ["game_id"])
    op.create_index("ix_important_quotes_note_id", "important_quotes", ["note_id"])

    # ── entities ───────────────────────────────────────────────────────────────
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
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
        sa.UniqueConstraint(
            "game_id", "entity_type", "name",
            name="uq_entities_game_entity_type_name",
        ),
    )
    op.create_index("ix_entities_game_id", "entities", ["game_id"])

    # ── threads ────────────────────────────────────────────────────────────────
    op.create_table(
        "threads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "is_resolved",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_note_id",
            sa.BigInteger(),
            sa.ForeignKey("notes.id"),
            nullable=True,
        ),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT is_resolved OR resolved_at IS NOT NULL",
            name="ck_threads_resolved_at_when_resolved",
        ),
    )
    op.create_index("ix_threads_game_id", "threads", ["game_id"])
    op.create_index(
        "ix_threads_game_open",
        "threads",
        ["game_id", "is_resolved"],
    )

    # ── player_characters ──────────────────────────────────────────────────────
    op.create_table(
        "player_characters",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
        ),
        sa.Column("character_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "game_id", "character_name",
            name="uq_player_characters_game_character",
        ),
    )
    op.create_index("ix_player_characters_game_id", "player_characters", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_player_characters_game_id", table_name="player_characters")
    op.drop_table("player_characters")

    op.drop_index("ix_threads_game_open", table_name="threads")
    op.drop_index("ix_threads_game_id", table_name="threads")
    op.drop_table("threads")

    op.drop_index("ix_entities_game_id", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_important_quotes_note_id", table_name="important_quotes")
    op.drop_index("ix_important_quotes_game_id", table_name="important_quotes")
    op.drop_table("important_quotes")

    op.drop_index("ix_combat_updates_note_id", table_name="combat_updates")
    op.drop_index("ix_combat_updates_game_id", table_name="combat_updates")
    op.drop_table("combat_updates")

    op.drop_table("notes_loot")

    op.drop_index("ix_loot_game_id", table_name="loot")
    op.drop_table("loot")

    op.drop_index("ix_decisions_note_id", table_name="decisions")
    op.drop_index("ix_decisions_game_id", table_name="decisions")
    op.drop_table("decisions")

    op.drop_table("notes_events")

    op.drop_index("ix_events_game_id", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_notes_game_id", table_name="notes")
    op.drop_table("notes")

    op.alter_column("transcripts", "text", new_column_name="transcript")
    op.drop_index("ix_transcripts_game_id_created_at", table_name="transcripts")
    op.drop_index("ix_transcripts_game_id", table_name="transcripts")
    op.drop_column("transcripts", "note_taker_processed")
    op.drop_column("transcripts", "game_id")

    op.drop_table("games")
