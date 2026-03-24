from datetime import datetime
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

VECTOR_DIM = 768


class Base(DeclarativeBase):
    pass


class EntityType(str, Enum):
    npc = "npc"
    location = "location"
    item = "item"
    faction = "faction"
    other = "other"


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # renamed from 'transcript' in migration 0003 to avoid table/column name collision
    text: Mapped[str] = mapped_column(Text, name="text", nullable=False)
    audio_window_start: Mapped[float] = mapped_column(Float, nullable=False)
    audio_window_end: Mapped[float] = mapped_column(Float, nullable=False)
    end_of_turn_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Added in migration 0003
    game_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("games.id"), nullable=True
    )
    note_taker_processed: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    world_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("hostname", "world_id", name="uq_games_hostname_world_id"),
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_transcript_ids: Mapped[list] = mapped_column(ARRAY(BigInteger), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "game_id", "entity_type", "name",
            name="uq_entities_game_entity_type_name",
        ),
    )


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_note_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("notes.id"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quest_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("quests.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "NOT is_resolved OR resolved_at IS NOT NULL",
            name="ck_threads_resolved_at_when_resolved",
        ),
    )


class PlayerCharacter(Base):
    __tablename__ = "player_characters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "game_id", "character_name",
            name="uq_player_characters_game_character",
        ),
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)
    __table_args__ = (UniqueConstraint("game_id", "text", name="uq_events_game_text"),)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    note_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notes.id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    made_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)


class Loot(Base):
    __tablename__ = "loot"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    acquired_by: Mapped[str] = mapped_column(String(255), nullable=False)
    quest_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("quests.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)
    __table_args__ = (UniqueConstraint("game_id", "item_name", "acquired_by", name="uq_loot_game_item_acquirer"),)


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    quest_giver_entity_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("entities.id"), nullable=True
    )
    note_ids: Mapped[list] = mapped_column(
        ARRAY(BigInteger), nullable=False, server_default=sa.text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)

    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_quests_game_name"),
    )


class QuestDescriptionHistory(Base):
    """Archived snapshot of a quest description before it was overwritten."""

    __tablename__ = "quest_description_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quests.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Informational reference — intentionally no FK so note deletion doesn't
    # cascade to history rows.
    note_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Association tables (join tables for many-to-many) ───────────────────────

notes_events_table = sa.Table(
    "notes_events",
    Base.metadata,
    sa.Column("note_id", BigInteger, sa.ForeignKey("notes.id"), primary_key=True),
    sa.Column("event_id", BigInteger, sa.ForeignKey("events.id"), primary_key=True),
)

notes_loot_table = sa.Table(
    "notes_loot",
    Base.metadata,
    sa.Column("note_id", BigInteger, sa.ForeignKey("notes.id"), primary_key=True),
    sa.Column("loot_id", BigInteger, sa.ForeignKey("loot.id"), primary_key=True),
)

notes_entities_table = sa.Table(
    "notes_entities",
    Base.metadata,
    sa.Column("note_id", BigInteger, sa.ForeignKey("notes.id"), primary_key=True),
    sa.Column("entity_id", BigInteger, sa.ForeignKey("entities.id"), primary_key=True),
)


class CombatUpdate(Base):
    __tablename__ = "combat_updates"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    note_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notes.id"), nullable=False)
    encounter: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)


class ImportantQuote(Base):
    __tablename__ = "important_quotes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id"), nullable=False)
    note_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notes.id"), nullable=False)
    transcript_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("transcripts.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
