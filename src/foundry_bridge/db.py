import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fastembed import TextEmbedding

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from foundry_bridge.models import (
    CombatUpdate,
    Decision,
    Entity,
    EntityType,
    Event,
    Game,
    ImportantQuote,
    Loot,
    Note,
    PlayerCharacter,
    Quest,
    QuestDescriptionHistory,
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

# ── FastEmbed model singleton ──────────────────────────────────────────────────

_FASTEMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
_embed_model: "TextEmbedding | None" = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding  # lazy import to avoid startup overhead
        _embed_model = TextEmbedding(model_name=_FASTEMBED_MODEL, threads=2)
    return _embed_model


async def _embed_texts(texts: list[str], *, as_query: bool = False) -> list[list[float]]:
    """Embed a batch of texts in a thread pool to avoid blocking the event loop."""
    prefix = "search_query: " if as_query else "search_document: "
    prefixed = [prefix + t for t in texts]
    model = _get_embed_model()
    return await asyncio.to_thread(lambda: [v.tolist() for v in model.embed(prefixed)])


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


@dataclass
class PipelineWriteResult:
    note_id: int
    entity_ids: list[int]
    new_thread_ids: list[int]
    resolved_thread_ids: list[int]
    event_ids: list[int]
    decision_ids: list[int]
    loot_ids: list[int]
    combat_ids: list[int]
    quest_ids: list[int]


async def write_note_pipeline_result(
    *,
    game_id: int,
    note_summary: str,
    source_transcript_ids: list[int],
    entities: list[dict],
    threads_opened: list[dict],  # list of {"text": str, "quest_id": Optional[int]}
    threads_closed: list[dict],  # list of {"id": int, "resolution": str}
    events: list[str],
    decisions: list[dict],       # list of {"decision": str, "made_by": str}
    loot: list[dict],            # list of {"item_name": str, "acquired_by": str, "quest_id": Optional[int]}
    combat_updates: list[dict],  # list of {"encounter": str, "outcome": str}
    important_quotes: list[dict],
    quests_opened: list[dict],   # list of {"name": str, "description": str, "quest_giver_entity_id": Optional[int]}
    quests_completed: list[str], # list of quest names
    quests_updated: list[dict],  # list of {"name": str, "description"?: str, "status"?: str, "quest_giver_entity_id"?: int}
) -> PipelineWriteResult:
    """Atomically persist all outputs from a note-generation pipeline run.

    On any exception the transaction rolls back; transcripts remain unprocessed and
    will be retried on the next poll cycle.
    """
    logger.info(
        "Writing note pipeline result: game_id=%d transcripts=%d entities=%d "
        "threads_opened=%d threads_closed=%d events=%d decisions=%d loot=%d combat=%d quotes=%d "
        "quests_opened=%d quests_completed=%d quests_updated=%d",
        game_id, len(source_transcript_ids), len(entities),
        len(threads_opened), len(threads_closed), len(events),
        len(decisions), len(loot), len(combat_updates), len(important_quotes),
        len(quests_opened), len(quests_completed), len(quests_updated),
    )
    inserted_entity_ids: list[int] = []
    inserted_thread_ids: list[int] = []
    resolved_thread_ids: list[int] = []
    inserted_event_ids: list[int] = []
    inserted_decision_ids: list[int] = []
    inserted_loot_ids: list[int] = []
    inserted_combat_ids: list[int] = []
    inserted_quest_ids: list[int] = []

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

            # 2. Upsert entities (accumulate descriptions); collect IDs via RETURNING
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
                        "description": entity_stmt.excluded.description,
                        "updated_at": sa.func.now(),
                    },
                ).returning(Entity.id)
                entity_result = await session.execute(entity_stmt)
                entity_id = entity_result.scalar()
                if entity_id is not None:
                    inserted_entity_ids.append(entity_id)

            # 3. Upsert quests from quests_opened (new active quests)
            for q in quests_opened:
                # Check whether the quest already exists so we can archive its
                # current description before overwriting it.
                existing_result = await session.execute(
                    sa.select(Quest.id, Quest.description).where(
                        Quest.game_id == game_id, Quest.name == q["name"]
                    )
                )
                existing_row = existing_result.one_or_none()

                if existing_row is not None:
                    existing_quest_id, old_description = existing_row
                    # Archive old description before overwriting
                    session.add(
                        QuestDescriptionHistory(
                            quest_id=existing_quest_id,
                            description=old_description,
                            note_id=note_id,
                        )
                    )
                    await session.execute(
                        sa.update(Quest)
                        .where(Quest.id == existing_quest_id)
                        .values(
                            description=q["description"],
                            note_ids=sa.func.array_append(Quest.note_ids, note_id),
                            updated_at=sa.func.now(),
                        )
                    )
                    inserted_quest_ids.append(existing_quest_id)
                else:
                    quest_stmt = pg_insert(Quest).values(
                        game_id=game_id,
                        name=q["name"],
                        description=q["description"],
                        status="active",
                        quest_giver_entity_id=q.get("quest_giver_entity_id"),
                        note_ids=[note_id],
                    ).returning(Quest.id)
                    quest_result = await session.execute(quest_stmt)
                    quest_id_val = quest_result.scalar()
                    if quest_id_val is not None:
                        inserted_quest_ids.append(quest_id_val)

            # 4. Mark quests as completed
            for quest_name in quests_completed:
                await session.execute(
                    sa.update(Quest)
                    .where(Quest.game_id == game_id, Quest.name == quest_name)
                    .values(
                        status="completed",
                        note_ids=sa.func.array_append(Quest.note_ids, note_id),
                        updated_at=sa.func.now(),
                    )
                )

            # 5. Upsert quests_updated (partial updates to existing quests)
            for qu in quests_updated:
                upd: dict = {
                    "note_ids": sa.func.array_append(Quest.note_ids, note_id),
                    "updated_at": sa.func.now(),
                }
                if qu.get("description") is not None:
                    # Archive old description before overwriting
                    prev_result = await session.execute(
                        sa.select(Quest.id, Quest.description).where(
                            Quest.game_id == game_id, Quest.name == qu["name"]
                        )
                    )
                    prev_row = prev_result.one_or_none()
                    if prev_row is not None:
                        prev_quest_id, old_description = prev_row
                        session.add(
                            QuestDescriptionHistory(
                                quest_id=prev_quest_id,
                                description=old_description,
                                note_id=note_id,
                            )
                        )
                    upd["description"] = qu["description"]
                if qu.get("status") is not None:
                    upd["status"] = qu["status"]
                if qu.get("quest_giver_entity_id") is not None:
                    upd["quest_giver_entity_id"] = qu["quest_giver_entity_id"]
                await session.execute(
                    sa.update(Quest)
                    .where(Quest.game_id == game_id, Quest.name == qu["name"])
                    .values(**upd)
                )

            # 6. Create new threads; collect IDs via flush
            for thread_data in threads_opened:
                text = thread_data["text"]
                raw_quest_id = thread_data.get("quest_id")
                safe_quest_id: Optional[int] = None
                if raw_quest_id is not None:
                    qcheck = await session.execute(
                        sa.select(Quest.id).where(
                            Quest.id == raw_quest_id, Quest.game_id == game_id
                        )
                    )
                    if qcheck.scalar():
                        safe_quest_id = raw_quest_id
                    else:
                        logger.warning(
                            "game %d: thread references unknown quest_id=%d; nullifying",
                            game_id, raw_quest_id,
                        )
                new_thread = Thread(game_id=game_id, text=text, quest_id=safe_quest_id)
                session.add(new_thread)
                await session.flush()
                inserted_thread_ids.append(new_thread.id)

            # 7. Resolve threads (three-tier validation: missing / cross-game / already resolved)
            if threads_closed:
                closed_ids = [t["id"] for t in threads_closed]
                resolutions = {t["id"]: t.get("resolution", "") for t in threads_closed}
                all_result = await session.execute(
                    sa.select(Thread.id, Thread.game_id, Thread.is_resolved).where(
                        Thread.id.in_(closed_ids)
                    )
                )
                thread_lookup = {row[0]: (row[1], row[2]) for row in all_result.all()}
                valid_ids: set[int] = set()
                for tid in closed_ids:
                    if tid not in thread_lookup:
                        logger.warning(
                            "game %d: thread_close: ID %d not found; skipping",
                            game_id, tid,
                        )
                    elif thread_lookup[tid][0] != game_id:
                        logger.error(
                            "game %d: thread_close: ID %d belongs to game %d "
                            "(cross-game access violation); skipping",
                            game_id, tid, thread_lookup[tid][0],
                        )
                    elif thread_lookup[tid][1]:  # already resolved
                        logger.warning(
                            "game %d: thread_close: ID %d already resolved; skipping",
                            game_id, tid,
                        )
                    else:
                        valid_ids.add(tid)
                resolved_thread_ids = list(valid_ids)
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

            # 8. Insert decisions; collect IDs via flush
            for d in decisions:
                d_obj = Decision(
                    game_id=game_id, note_id=note_id,
                    decision=d["decision"], made_by=d["made_by"],
                )
                session.add(d_obj)
                await session.flush()
                inserted_decision_ids.append(d_obj.id)

            # 9. Upsert events + m2m link to note; collect IDs
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
                inserted_event_ids.append(event_id)
                await session.execute(
                    pg_insert(notes_events_table)
                    .values(note_id=note_id, event_id=event_id)
                    .on_conflict_do_nothing()
                )

            # 7. Upsert loot + m2m link to note; collect IDs
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
                inserted_loot_ids.append(loot_id)
                await session.execute(
                    pg_insert(notes_loot_table)
                    .values(note_id=note_id, loot_id=loot_id)
                    .on_conflict_do_nothing()
                )
                # Link loot to a quest if provided and valid
                raw_loot_quest_id = item.get("quest_id")
                if raw_loot_quest_id is not None:
                    lqcheck = await session.execute(
                        sa.select(Quest.id).where(
                            Quest.id == raw_loot_quest_id, Quest.game_id == game_id
                        )
                    )
                    if lqcheck.scalar():
                        await session.execute(
                            sa.update(Loot)
                            .where(Loot.id == loot_id)
                            .values(quest_id=raw_loot_quest_id)
                        )
                    else:
                        logger.warning(
                            "game %d: loot '%s' references unknown quest_id=%d; ignoring",
                            game_id, item["item_name"], raw_loot_quest_id,
                        )

            # 11. Insert combat_updates; collect IDs via flush
            for c in combat_updates:
                c_obj = CombatUpdate(
                    game_id=game_id, note_id=note_id,
                    encounter=c["encounter"], outcome=c["outcome"],
                )
                session.add(c_obj)
                await session.flush()
                inserted_combat_ids.append(c_obj.id)

            # 12. Insert important_quotes (validate transcript_id against current batch)
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

            # 13. Mark all source transcripts as processed
            await session.execute(
                sa.update(Transcript)
                .where(Transcript.id.in_(source_transcript_ids))
                .values(note_taker_processed=True)
            )
    logger.info(
        "Note pipeline result committed: game_id=%d note_id=%d",
        game_id, note_id,
    )
    return PipelineWriteResult(
        note_id=note_id,
        entity_ids=inserted_entity_ids,
        new_thread_ids=inserted_thread_ids,
        resolved_thread_ids=resolved_thread_ids,
        event_ids=inserted_event_ids,
        decision_ids=inserted_decision_ids,
        loot_ids=inserted_loot_ids,
        combat_ids=inserted_combat_ids,
        quest_ids=inserted_quest_ids,
    )


# ── Hybrid vector+text search helpers ─────────────────────────────────────────

_RRF_K = 60  # standard Reciprocal Rank Fusion constant


def _rrf_merge(vector_rows: list, text_rows: list, *, k: int) -> list:
    """Merge two ranked lists via Reciprocal Rank Fusion; return top-k unique items."""
    scores: dict[int, float] = {}
    seen: dict[int, object] = {}
    for rank, row in enumerate(vector_rows, start=1):
        scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (_RRF_K + rank)
        seen[row.id] = row
    for rank, row in enumerate(text_rows, start=1):
        scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (_RRF_K + rank)
        seen[row.id] = row
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    return [seen[rid] for rid in ranked[:k]]


async def search_entities(
    game_id: int,
    query: str,
    *,
    entity_type: Optional[EntityType] = None,
    k: int = 8,
) -> list[Entity]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3
    type_filter = [Entity.entity_type == entity_type] if entity_type else []

    async def _vec() -> list[Entity]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Entity)
                .where(Entity.game_id == game_id, Entity.embedding.is_not(None), *type_filter)
                .order_by(Entity.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Entity]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Entity)
                .where(
                    Entity.game_id == game_id,
                    sa.func.to_tsvector(
                        "english",
                        sa.func.concat(
                            Entity.entity_type, " ", Entity.name, " ",
                            sa.func.coalesce(Entity.description, ""),
                        ),
                    ).op("@@")(sa.func.plainto_tsquery("english", query)),
                    *type_filter,
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_open_threads(game_id: int, query: str, k: int = 6) -> list[Thread]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Thread]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Thread)
                .where(
                    Thread.game_id == game_id,
                    Thread.is_resolved == False,  # noqa: E712
                    Thread.embedding.is_not(None),
                )
                .order_by(Thread.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Thread]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Thread)
                .where(
                    Thread.game_id == game_id,
                    Thread.is_resolved == False,  # noqa: E712
                    sa.func.to_tsvector("english", Thread.text)
                    .op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_resolved_threads(game_id: int, query: str, k: int = 6) -> list[Thread]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Thread]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Thread)
                .where(
                    Thread.game_id == game_id,
                    Thread.is_resolved == True,  # noqa: E712
                    Thread.embedding.is_not(None),
                )
                .order_by(Thread.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Thread]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Thread)
                .where(
                    Thread.game_id == game_id,
                    Thread.is_resolved == True,  # noqa: E712
                    sa.func.to_tsvector("english", Thread.text)
                    .op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_events(game_id: int, query: str, k: int = 8) -> list[Event]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Event]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Event)
                .where(Event.game_id == game_id, Event.embedding.is_not(None))
                .order_by(Event.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Event]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Event)
                .where(
                    Event.game_id == game_id,
                    sa.func.to_tsvector("english", Event.text)
                    .op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_notes(game_id: int, query: str, k: int = 4) -> list[Note]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Note]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Note)
                .where(Note.game_id == game_id, Note.embedding.is_not(None))
                .order_by(Note.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Note]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Note)
                .where(
                    Note.game_id == game_id,
                    sa.func.to_tsvector("english", Note.summary)
                    .op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_decisions(game_id: int, query: str, k: int = 6) -> list[Decision]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Decision]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Decision)
                .where(Decision.game_id == game_id, Decision.embedding.is_not(None))
                .order_by(Decision.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Decision]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Decision)
                .where(
                    Decision.game_id == game_id,
                    sa.func.to_tsvector(
                        "english",
                        sa.func.concat(
                            sa.func.coalesce(Decision.made_by, ""), " ", Decision.decision
                        ),
                    ).op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_loot(game_id: int, query: str, k: int = 6) -> list[Loot]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Loot]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Loot)
                .where(Loot.game_id == game_id, Loot.embedding.is_not(None))
                .order_by(Loot.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Loot]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Loot)
                .where(
                    Loot.game_id == game_id,
                    sa.func.to_tsvector(
                        "english",
                        sa.func.concat(
                            Loot.item_name, " ", sa.func.coalesce(Loot.acquired_by, "")
                        ),
                    ).op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)


async def search_combat(game_id: int, query: str, k: int = 6) -> list[CombatUpdate]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[CombatUpdate]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(CombatUpdate)
                .where(CombatUpdate.game_id == game_id, CombatUpdate.embedding.is_not(None))
                .order_by(CombatUpdate.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[CombatUpdate]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(CombatUpdate)
                .where(
                    CombatUpdate.game_id == game_id,
                    sa.func.to_tsvector(
                        "english",
                        sa.func.concat(CombatUpdate.encounter, " ", CombatUpdate.outcome),
                    ).op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)

async def search_quests(game_id: int, query: str, k: int = 8) -> list[Quest]:
    query_vec = (await _embed_texts([query], as_query=True))[0]
    fetch = k * 3

    async def _vec() -> list[Quest]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Quest)
                .where(Quest.game_id == game_id, Quest.embedding.is_not(None))
                .order_by(Quest.embedding.cosine_distance(query_vec))
                .limit(fetch)
            )
            return list(result.scalars().all())

    async def _txt() -> list[Quest]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sa.select(Quest)
                .where(
                    Quest.game_id == game_id,
                    sa.func.to_tsvector(
                        "english",
                        sa.func.concat(Quest.name, " ", sa.func.coalesce(Quest.description, "")),
                    ).op("@@")(sa.func.plainto_tsquery("english", query)),
                )
                .limit(fetch)
            )
            return list(result.scalars().all())

    vec_rows, txt_rows = await asyncio.gather(_vec(), _txt())
    return _rrf_merge(vec_rows, txt_rows, k=k)



async def embed_unembedded_rows(game_id: int) -> None:
    """Best-effort: compute embeddings for any rows that are missing them.

    Called before each agent run so the search tools always have fresh data.
    Silently swallows errors — rows will be retried on the next pipeline run.

    Structured in three phases so ONNX inference runs outside any DB transaction.
    """
    table_specs = [
        (Entity,       lambda e: f"[{e.entity_type}] {e.name}: {e.description}"),
        (Thread,       lambda t: f"{t.text} \u2014 Resolution: {t.resolution or ''}" if t.is_resolved else t.text),
        (Event,        lambda e: e.text),
        (Note,         lambda n: n.summary),
        (Decision,     lambda d: f"Decision by {d.made_by}: {d.decision}"),
        (Loot,         lambda loot: f"Loot acquired by {loot.acquired_by}: {loot.item_name}"),
        (CombatUpdate, lambda c: f"Combat encounter: {c.encounter} \u2014 Outcome: {c.outcome}"),
        (Quest,        lambda q: f"[Quest] {q.name}: {q.description}"),
    ]
    try:
        # Phase 1: Collect (model_cls, pk, text) via short read session
        to_embed: list[tuple[type, int, str]] = []
        async with AsyncSessionLocal() as session:
            for model_cls, text_fn in table_specs:
                result = await session.execute(
                    sa.select(model_cls).where(
                        model_cls.game_id == game_id,
                        model_cls.embedding.is_(None),
                    )
                )
                for row in result.scalars().all():
                    to_embed.append((model_cls, row.id, text_fn(row)))

        if not to_embed:
            return

        # Phase 2: ONNX inference — outside any DB transaction
        model_classes, pks, texts = zip(*to_embed)
        vecs = await _embed_texts(list(texts))

        # Phase 3: Short write transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                for model_cls, pk, vec in zip(model_classes, pks, vecs):
                    obj = await session.get(model_cls, pk)
                    if obj is not None:
                        obj.embedding = vec  # type: ignore[attr-defined]
    except Exception:
        logger.exception("embed_unembedded_rows failed for game %d", game_id)


async def _write_embeddings_for_pipeline_result(result: PipelineWriteResult) -> None:
    """Post-commit: compute and store embeddings for all rows from a pipeline run.

    Best-effort: failures leave rows with embedding IS NULL, which embed_unembedded_rows
    will fill on the next pipeline run.

    Structured in three phases to keep the DB transaction short:
      1. Short read — collect (model_class, pk, text) tuples.
      2. ONNX inference — outside any DB transaction.
      3. Short write — update embedding columns.
    """
    try:
        # Phase 1: Collect (model_class, pk, text) with a short read session (no explicit txn needed)
        to_embed: list[tuple[type, int, str]] = []
        async with AsyncSessionLocal() as session:
            # Entities: re-fetch to get actual stored description after upsert merge
            for eid in result.entity_ids:
                entity = await session.get(Entity, eid)
                if entity:
                    to_embed.append((Entity, eid, f"[{entity.entity_type}] {entity.name}: {entity.description}"))

            # New threads
            for tid in result.new_thread_ids:
                thread = await session.get(Thread, tid)
                if thread:
                    to_embed.append((Thread, tid, thread.text))

            # Resolved threads: embed combined text with resolution
            for tid in result.resolved_thread_ids:
                thread = await session.get(Thread, tid)
                if thread:
                    combined = f"{thread.text} — Resolution: {thread.resolution or ''}"
                    to_embed.append((Thread, tid, combined))

            # Events
            for eid in result.event_ids:
                event = await session.get(Event, eid)
                if event:
                    to_embed.append((Event, eid, event.text))

            # Note
            note = await session.get(Note, result.note_id)
            if note:
                to_embed.append((Note, result.note_id, note.summary))

            # Decisions
            for did in result.decision_ids:
                decision = await session.get(Decision, did)
                if decision:
                    to_embed.append((Decision, did, f"Decision by {decision.made_by}: {decision.decision}"))

            # Loot
            for lid in result.loot_ids:
                loot_row = await session.get(Loot, lid)
                if loot_row:
                    to_embed.append((Loot, lid, f"Loot acquired by {loot_row.acquired_by}: {loot_row.item_name}"))

            # Combat
            for cid in result.combat_ids:
                combat = await session.get(CombatUpdate, cid)
                if combat:
                    to_embed.append((CombatUpdate, cid, f"Combat encounter: {combat.encounter} — Outcome: {combat.outcome}"))

            # Quests
            for qid in result.quest_ids:
                quest = await session.get(Quest, qid)
                if quest:
                    to_embed.append((Quest, qid, f"[Quest] {quest.name}: {quest.description}"))

        if not to_embed:
            return

        # Phase 2: ONNX inference — outside any DB transaction
        model_classes, pks, texts = zip(*to_embed)
        vecs = await _embed_texts(list(texts))

        # Phase 3: Short write transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                for model_cls, pk, vec in zip(model_classes, pks, vecs):
                    obj = await session.get(model_cls, pk)
                    if obj is not None:
                        obj.embedding = vec  # type: ignore[attr-defined]
    except Exception:
        logger.exception(
            "Failed to write embeddings for pipeline result (note_id=%d); "
            "rows will be retried by embed_unembedded_rows",
            result.note_id,
        )
