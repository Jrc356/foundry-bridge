import logging
import os

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from foundry_bridge.models import (
    CombatUpdate,
    Decision,
    Entity,
    Event,
    Game,
    ImportantQuote,
    Loot,
    Note,
    PlayerCharacter,
    Thread,
    Transcript,
    notes_events_table,
    notes_loot_table,
)

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ["DATABASE_URL"]

# Accept plain postgresql:// URLs and convert to the asyncpg scheme.
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_engine = create_async_engine(_DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_or_create_game(hostname: str, world_id: str, name: str) -> Game:
    """Insert or update a game record; return the persisted Game row."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = pg_insert(Game).values(hostname=hostname, world_id=world_id, name=name)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_games_hostname_world_id",
                set_={"name": stmt.excluded.name},
            ).returning(Game)
            result = await session.scalars(
                stmt, execution_options={"populate_existing": True}
            )
            game = result.one()
    logger.debug("Game upserted: id=%d hostname=%s world_id=%s", game.id, hostname, world_id)
    return game


async def store_transcript(
    *,
    participant_id: str,
    character_name: str,
    game_id: int,
    turn_index: int,
    text: str,
    audio_window_start: float,
    audio_window_end: float,
    end_of_turn_confidence: float,
) -> None:
    """Persist a single transcribed turn."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                Transcript(
                    participant_id=participant_id,
                    character_name=character_name,
                    game_id=game_id,
                    turn_index=turn_index,
                    text=text,
                    audio_window_start=audio_window_start,
                    audio_window_end=audio_window_end,
                    end_of_turn_confidence=end_of_turn_confidence,
                )
            )
    logger.debug(
        "Transcript stored: game_id=%d char=%s turn=%d confidence=%.2f",
        game_id, character_name, turn_index, end_of_turn_confidence,
    )


async def get_game_ids_with_unprocessed_transcripts() -> list[int]:
    """Return distinct game_id values that have at least one unprocessed transcript."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Transcript.game_id)
            .where(
                Transcript.game_id.is_not(None),
                Transcript.note_taker_processed == False,  # noqa: E712
            )
            .distinct()
        )
        game_ids = [row[0] for row in result.all()]
        logger.debug("Games with unprocessed transcripts: %d", len(game_ids))
        return game_ids


async def get_unprocessed_transcripts_for_game(game_id: int) -> list[Transcript]:
    """Return all unprocessed transcripts for a game, ordered by creation time."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Transcript)
            .where(
                Transcript.game_id == game_id,
                Transcript.note_taker_processed == False,  # noqa: E712
            )
            .order_by(Transcript.created_at)
        )
        rows = list(result.scalars().all())
        logger.debug("Unprocessed transcripts for game %d: %d", game_id, len(rows))
        return rows


async def upsert_player_characters(game_id: int, character_names: list[str]) -> None:
    """Add new player character names for a game; ignore names that already exist."""
    if not character_names:
        return
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for name in character_names:
                stmt = (
                    pg_insert(PlayerCharacter)
                    .values(game_id=game_id, character_name=name)
                    .on_conflict_do_nothing(constraint="uq_player_characters_game_character")
                )
                await session.execute(stmt)


async def get_player_characters_for_game(game_id: int) -> list[PlayerCharacter]:
    """Return all known player characters for a game."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(PlayerCharacter).where(PlayerCharacter.game_id == game_id)
        )
        return list(result.scalars().all())


async def get_open_threads_for_game(game_id: int) -> list[Thread]:
    """Return all unresolved threads for a game."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Thread).where(
                Thread.game_id == game_id,
                Thread.is_resolved == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())


async def get_resolved_threads_for_game(game_id: int) -> list[Thread]:
    """Return all resolved threads for a game (passed to LLM to prevent re-opening)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Thread).where(
                Thread.game_id == game_id,
                Thread.is_resolved == True,  # noqa: E712
            ).order_by(Thread.created_at)
        )
        return list(result.scalars().all())


async def get_entities_for_game(game_id: int) -> list[Entity]:
    """Return all entities for a game."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Entity).where(Entity.game_id == game_id).order_by(Entity.name)
        )
        return list(result.scalars().all())


async def get_recent_notes_for_game(game_id: int, limit: int = 3) -> list[Note]:
    """Return the most recent notes for a game, oldest-first."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Note)
            .where(Note.game_id == game_id)
            .order_by(Note.created_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        return list(reversed(rows))  # return oldest-first


async def get_events_for_game(game_id: int) -> list[Event]:
    """Return all events for a game (used as LLM context for deduplication)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Event).where(Event.game_id == game_id).order_by(Event.created_at)
        )
        return list(result.scalars().all())


async def write_note_pipeline_result(
    *,
    game_id: int,
    note_summary: str,
    source_transcript_ids: list[int],
    entities: list[dict],
    threads_opened: list[str],
    threads_closed: list[dict],  # list of {"id": int, "resolution": str}
    events: list[str],
    decisions: list[dict],       # list of {"decision": str, "made_by": str}
    loot: list[dict],            # list of {"item_name": str, "acquired_by": str}
    combat_updates: list[dict],  # list of {"encounter": str, "outcome": str}
    important_quotes: list[dict],
) -> None:
    """Atomically persist all outputs from a note-generation pipeline run.

    On any exception the transaction rolls back; transcripts remain unprocessed and
    will be retried on the next poll cycle.
    """
    logger.info(
        "Writing note pipeline result: game_id=%d transcripts=%d entities=%d "
        "threads_opened=%d threads_closed=%d events=%d decisions=%d loot=%d combat=%d quotes=%d",
        game_id, len(source_transcript_ids), len(entities),
        len(threads_opened), len(threads_closed), len(events),
        len(decisions), len(loot), len(combat_updates), len(important_quotes),
    )
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Create the note header row
            note = Note(
                game_id=game_id,
                summary=note_summary,
                source_transcript_ids=source_transcript_ids,
            )
            session.add(note)
            await session.flush()  # populate note.id before inserting children
            note_id = note.id

            # 2. Upsert entities (accumulate descriptions)
            for e in entities:
                entity_stmt = pg_insert(Entity).values(
                    game_id=game_id,
                    entity_type=e["entity_type"],
                    name=e["name"],
                    description=e["description"],
                )
                entity_stmt = entity_stmt.on_conflict_do_update(
                    constraint="uq_entities_game_entity_type_name",
                    set_={
                        "description": sa.func.concat(
                            Entity.description, "\n\n", entity_stmt.excluded.description
                        ),
                        "updated_at": sa.func.now(),
                    },
                )
                await session.execute(entity_stmt)

            # 3. Create new threads
            for text in threads_opened:
                session.add(Thread(game_id=game_id, text=text))

            # 4. Resolve threads (only for this game; log unknown/already-resolved IDs)
            if threads_closed:
                closed_ids = [t["id"] for t in threads_closed]
                resolutions = {t["id"]: t.get("resolution", "") for t in threads_closed}
                valid_result = await session.execute(
                    sa.select(Thread.id).where(
                        Thread.id.in_(closed_ids),
                        Thread.game_id == game_id,
                        Thread.is_resolved == False,  # noqa: E712
                    )
                )
                valid_ids = {row[0] for row in valid_result.all()}
                invalid_ids = set(closed_ids) - valid_ids
                if invalid_ids:
                    logger.warning(
                        "game %d: thread IDs %s not found or already resolved; skipping",
                        game_id, invalid_ids,
                    )
                for tid in valid_ids:
                    await session.execute(
                        sa.update(Thread)
                        .where(Thread.id == tid)
                        .values(
                            is_resolved=True,
                            resolved_at=sa.func.now(),
                            resolved_by_note_id=note_id,
                            resolution=resolutions.get(tid, ""),
                        )
                    )

            # 5. Insert decisions (each linked directly to the note)
            for d in decisions:
                session.add(Decision(
                    game_id=game_id, note_id=note_id,
                    decision=d["decision"], made_by=d["made_by"],
                ))

            # 6. Upsert events + m2m link to note
            for text in events:
                event_stmt = (
                    pg_insert(Event)
                    .values(game_id=game_id, text=text)
                    .on_conflict_do_nothing(constraint="uq_events_game_text")
                    .returning(Event.id)
                )
                event_result = await session.execute(event_stmt)
                event_id = event_result.scalar()
                if event_id is None:
                    # Row already existed — fetch its ID
                    existing = await session.execute(
                        sa.select(Event.id).where(
                            Event.game_id == game_id, Event.text == text
                        )
                    )
                    event_id = existing.scalar_one()
                await session.execute(
                    pg_insert(notes_events_table)
                    .values(note_id=note_id, event_id=event_id)
                    .on_conflict_do_nothing()
                )

            # 7. Upsert loot + m2m link to note
            for item in loot:
                acquired_by = item.get("acquired_by") or "the party"
                loot_stmt = pg_insert(Loot).values(
                    game_id=game_id,
                    item_name=item["item_name"],
                    acquired_by=acquired_by,
                )
                loot_stmt = loot_stmt.on_conflict_do_nothing(
                    constraint="uq_loot_game_item_acquirer"
                ).returning(Loot.id)
                loot_result = await session.execute(loot_stmt)
                loot_id = loot_result.scalar()
                if loot_id is None:
                    existing = await session.execute(
                        sa.select(Loot.id).where(
                            Loot.game_id == game_id,
                            Loot.item_name == item["item_name"],
                            Loot.acquired_by == acquired_by,
                        )
                    )
                    loot_id = existing.scalar_one()
                await session.execute(
                    pg_insert(notes_loot_table)
                    .values(note_id=note_id, loot_id=loot_id)
                    .on_conflict_do_nothing()
                )

            # 8. Insert combat_updates (each linked directly to the note)
            for c in combat_updates:
                session.add(CombatUpdate(
                    game_id=game_id, note_id=note_id,
                    encounter=c["encounter"], outcome=c["outcome"],
                ))

            # 9. Insert important_quotes (validate transcript_id against current batch)
            valid_transcript_ids = set(source_transcript_ids)
            for q in important_quotes:
                raw_tid = q.get("transcript_id")
                safe_tid = raw_tid if raw_tid in valid_transcript_ids else None
                if raw_tid is not None and safe_tid is None:
                    logger.warning(
                        "important_quote transcript_id %s not in source batch; nullifying", raw_tid
                    )
                session.add(ImportantQuote(
                    game_id=game_id, note_id=note_id,
                    transcript_id=safe_tid,
                    text=q["text"],
                    speaker=q.get("speaker"),
                ))

            # 10. Mark all source transcripts as processed
            await session.execute(
                sa.update(Transcript)
                .where(Transcript.id.in_(source_transcript_ids))
                .values(note_taker_processed=True)
            )
    logger.info(
        "Note pipeline result committed: game_id=%d note_id=%d",
        game_id, note_id,
    )
