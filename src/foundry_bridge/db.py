import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, NamedTuple, Optional

if TYPE_CHECKING:
    from fastembed import TextEmbedding

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from foundry_bridge.models import (
    AuditFlag,
    AuditRun,
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
    notes_entities_table,
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
                Thread.is_deleted == False,  # noqa: E712
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
                Thread.is_deleted == False,  # noqa: E712
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


async def get_quests_for_game(game_id: int) -> list[Quest]:
    """Return all non-deleted quests for a game."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Quest)
            .where(
                Quest.game_id == game_id,
                Quest.is_deleted == False,  # noqa: E712
            )
            .order_by(Quest.created_at)
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


async def get_entity_for_game_by_id(game_id: int, entity_id: int) -> Optional[Entity]:
    """Return an entity by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        entity = await session.get(Entity, entity_id)
        if entity is None or entity.game_id != game_id:
            return None
        return entity


async def get_thread_for_game_by_id(game_id: int, thread_id: int) -> Optional[Thread]:
    """Return a thread by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        thread = await session.get(Thread, thread_id)
        if thread is None or thread.game_id != game_id:
            return None
        return thread


async def get_quest_for_game_by_id(game_id: int, quest_id: int) -> Optional[Quest]:
    """Return a quest by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        quest = await session.get(Quest, quest_id)
        if quest is None or quest.game_id != game_id:
            return None
        return quest


async def get_event_for_game_by_id(game_id: int, event_id: int) -> Optional[Event]:
    """Return an event by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        event = await session.get(Event, event_id)
        if event is None or event.game_id != game_id:
            return None
        return event


async def get_decision_for_game_by_id(game_id: int, decision_id: int) -> Optional[Decision]:
    """Return a decision by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        decision = await session.get(Decision, decision_id)
        if decision is None or decision.game_id != game_id:
            return None
        return decision


async def get_loot_for_game_by_id(game_id: int, loot_id: int) -> Optional[Loot]:
    """Return loot by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        loot = await session.get(Loot, loot_id)
        if loot is None or loot.game_id != game_id:
            return None
        return loot


async def get_note_for_game_by_id(game_id: int, note_id: int) -> Optional[Note]:
    """Return a note by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        note = await session.get(Note, note_id)
        if note is None or note.game_id != game_id:
            return None
        return note


async def get_combat_for_game_by_id(game_id: int, combat_id: int) -> Optional[CombatUpdate]:
    """Return a combat row by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        combat = await session.get(CombatUpdate, combat_id)
        if combat is None or combat.game_id != game_id:
            return None
        return combat


async def get_quote_for_game_by_id(game_id: int, quote_id: int) -> Optional[ImportantQuote]:
    """Return an important quote by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        quote = await session.get(ImportantQuote, quote_id)
        if quote is None or quote.game_id != game_id:
            return None
        return quote


async def get_transcript_for_game_by_id(game_id: int, transcript_id: int) -> Optional[Transcript]:
    """Return a transcript row by ID scoped to game_id, or None if missing/out-of-game."""
    async with AsyncSessionLocal() as session:
        transcript = await session.get(Transcript, transcript_id)
        if transcript is None or transcript.game_id != game_id:
            return None
        return transcript


async def get_last_audit_run_for_game(game_id: int) -> Optional[AuditRun]:
    """Return the most recent completed audit run for a game."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(AuditRun)
            .where(
                AuditRun.game_id == game_id,
                AuditRun.status == "completed",
            )
            .order_by(AuditRun.completed_at.desc(), AuditRun.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_running_audit_run_for_game(game_id: int) -> Optional[AuditRun]:
    """Return the current running audit run for a game, if any."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(AuditRun)
            .where(
                AuditRun.game_id == game_id,
                AuditRun.status == "running",
            )
            .order_by(AuditRun.triggered_at.desc(), AuditRun.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_notes_since_last_audit(game_id: int, since_note_id: Optional[int]) -> list[Note]:
    """Return non-audit notes newer than since_note_id for the game."""
    predicates = [
        Note.game_id == game_id,
        Note.is_audit == False,  # noqa: E712
    ]
    if since_note_id is not None:
        predicates.append(Note.id > since_note_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Note).where(*predicates).order_by(Note.id)
        )
        return list(result.scalars().all())


async def get_transcripts_for_notes(note_ids: list[int]) -> list[Transcript]:
    """Return transcripts referenced by the provided note IDs."""
    if not note_ids:
        return []

    async with AsyncSessionLocal() as session:
        note_result = await session.execute(
            sa.select(Note.source_transcript_ids).where(Note.id.in_(note_ids))
        )
        transcript_ids: list[int] = []
        seen: set[int] = set()
        for row in note_result.all():
            source_ids = row[0] or []
            for tid in source_ids:
                if tid not in seen:
                    seen.add(tid)
                    transcript_ids.append(tid)

        if not transcript_ids:
            return []

        result = await session.execute(
            sa.select(Transcript)
            .where(Transcript.id.in_(transcript_ids))
            .order_by(Transcript.created_at, Transcript.id)
        )
        return list(result.scalars().all())


async def get_unaudited_note_count(game_id: int) -> int:
    """Return count of non-audit notes newer than the latest completed audit window."""
    last_run = await get_last_audit_run_for_game(game_id)
    since_note_id = last_run.max_note_id if last_run is not None else None

    predicates = [
        Note.game_id == game_id,
        Note.is_audit == False,  # noqa: E712
    ]
    if since_note_id is not None:
        predicates.append(Note.id > since_note_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(sa.func.count(Note.id)).where(*predicates)
        )
        return int(result.scalar_one() or 0)


async def get_all_entities_for_game(game_id: int) -> list[Entity]:
    """Return all entities for a game."""
    return await get_entities_for_game(game_id)


async def get_all_quests_for_game(game_id: int) -> list[Quest]:
    """Return all non-deleted quests for a game."""
    return await get_quests_for_game(game_id)


async def get_all_open_threads_for_game(game_id: int) -> list[Thread]:
    """Return all non-deleted open threads for a game."""
    return await get_open_threads_for_game(game_id)


async def create_audit_run(game_id: int, trigger_source: str) -> AuditRun:
    """Create and return a new running audit run row."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            run = AuditRun(
                game_id=game_id,
                trigger_source=trigger_source,
                status="running",
                heartbeat_at=sa.func.now(),
            )
            session.add(run)
            await session.flush()
            await session.refresh(run)
        return run


async def touch_audit_run_heartbeat(audit_run_id: int) -> bool:
    """Update heartbeat timestamp for a running audit run."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                sa.update(AuditRun)
                .where(
                    AuditRun.id == audit_run_id,
                    AuditRun.status == "running",
                )
                .values(heartbeat_at=sa.func.now())
            )
            return _affected_rows(result) > 0


async def fail_audit_run(audit_run_id: int) -> bool:
    """Mark an audit run as failed."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                sa.update(AuditRun)
                .where(AuditRun.id == audit_run_id)
                .values(
                    status="failed",
                    completed_at=sa.func.now(),
                    heartbeat_at=sa.func.now(),
                )
            )
            return _affected_rows(result) > 0


async def complete_audit_run_noop(audit_run_id: int) -> bool:
    """Mark a running audit as completed with an empty note window."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                sa.update(AuditRun)
                .where(
                    AuditRun.id == audit_run_id,
                    AuditRun.status == "running",
                )
                .values(
                    status="completed",
                    completed_at=sa.func.now(),
                    heartbeat_at=sa.func.now(),
                    notes_audited=[],
                    notes_audited_count=0,
                    min_note_id=None,
                    max_note_id=None,
                    audit_note_id=None,
                )
            )
            return _affected_rows(result) > 0


async def delete_audit_run_if_running(audit_run_id: int) -> bool:
    """Delete a pre-created audit run row if it is still running."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                sa.delete(AuditRun).where(
                    AuditRun.id == audit_run_id,
                    AuditRun.status == "running",
                )
            )
            return _affected_rows(result) > 0


async def reset_stale_audit_runs(stale_after_minutes: int = 15) -> int:
    """Fail running audit rows that have not heartbeated within stale_after_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                sa.update(AuditRun)
                .where(
                    AuditRun.status == "running",
                    sa.func.coalesce(AuditRun.heartbeat_at, AuditRun.triggered_at) < cutoff,
                )
                .values(
                    status="failed",
                    completed_at=sa.func.now(),
                    heartbeat_at=sa.func.now(),
                )
            )
            stale_count = _affected_rows(result)
            if stale_count:
                logger.warning(
                    "Reset %d stale audit runs older than %d minutes",
                    stale_count,
                    stale_after_minutes,
                )
            return stale_count


async def restore_deleted_quest(game_id: int, quest_id: int) -> dict[str, Any]:
    """Restore a soft-deleted quest."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            quest = await session.get(Quest, quest_id)
            if quest is None or quest.game_id != game_id:
                return {
                    "ok": False,
                    "noop": False,
                    "reason_code": "not_found",
                    "message": "Quest not found for game",
                }

            if not quest.is_deleted:
                return {
                    "ok": True,
                    "noop": True,
                    "reason_code": "already_active",
                    "message": "Quest is already active",
                    "quest_id": quest_id,
                }

            await session.execute(
                sa.update(Quest)
                .where(Quest.id == quest_id, Quest.game_id == game_id)
                .values(
                    is_deleted=False,
                    deleted_at=None,
                    deleted_reason=None,
                    updated_at=sa.func.now(),
                )
            )
            return {
                "ok": True,
                "noop": False,
                "reason_code": "restored",
                "message": "Quest restored",
                "quest_id": quest_id,
            }


async def restore_deleted_thread(game_id: int, thread_id: int) -> dict[str, Any]:
    """Restore a soft-deleted thread."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            thread = await session.get(Thread, thread_id)
            if thread is None or thread.game_id != game_id:
                return {
                    "ok": False,
                    "noop": False,
                    "reason_code": "not_found",
                    "message": "Thread not found for game",
                }

            if not thread.is_deleted:
                return {
                    "ok": True,
                    "noop": True,
                    "reason_code": "already_active",
                    "message": "Thread is already active",
                    "thread_id": thread_id,
                }

            await session.execute(
                sa.update(Thread)
                .where(Thread.id == thread_id, Thread.game_id == game_id)
                .values(
                    is_deleted=False,
                    deleted_at=None,
                    deleted_reason=None,
                )
            )
            return {
                "ok": True,
                "noop": False,
                "reason_code": "restored",
                "message": "Thread restored",
                "thread_id": thread_id,
            }


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


@dataclass
class AuditPipelineResult:
    audit_run_id: int
    audit_note_id: int
    entity_ids: list[int]
    thread_ids: list[int]
    event_ids: list[int]
    decision_ids: list[int]
    loot_ids: list[int]
    quest_ids: list[int]
    combat_ids: list[int]


@dataclass
class AuditFlagMutationResult:
    flag_id: int
    ok: bool
    noop: bool
    status: Optional[str]
    reason_code: str
    message: str
    details: dict[str, Any]


class FlagApplyResult(NamedTuple):
    ok: bool
    noop: bool
    reason_code: str
    message: str
    details: dict[str, Any]
    embed_ids: dict[str, list[int]]


def _model_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return payload
    raise TypeError(f"Expected dict-like output item, got {type(obj)!r}")


def _model_list_to_dicts(items: Any) -> list[dict[str, Any]]:
    if not items:
        return []
    return [_model_to_dict(item) for item in items]


def _flag_result(
    *,
    flag_id: int,
    ok: bool,
    noop: bool,
    status: Optional[str],
    reason_code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> AuditFlagMutationResult:
    return AuditFlagMutationResult(
        flag_id=flag_id,
        ok=ok,
        noop=noop,
        status=status,
        reason_code=reason_code,
        message=message,
        details=details or {},
    )


def _affected_rows(result: Any) -> int:
    rowcount = getattr(result, "rowcount", None)
    return int(rowcount or 0)


def _canonicalize_audit_table_name(raw_table_name: Any) -> Optional[str]:
    if not isinstance(raw_table_name, str):
        return None

    table_aliases = {
        "quest": "quests",
        "quests": "quests",
        "thread": "threads",
        "threads": "threads",
        "entity": "entities",
        "entities": "entities",
        "event": "events",
        "events": "events",
        "loot": "loot",
        "loots": "loot",
        "decision": "decisions",
        "decisions": "decisions",
        "quote": "important_quotes",
        "quotes": "important_quotes",
        "important_quote": "important_quotes",
        "important_quotes": "important_quotes",
        "combat_update": "combat_updates",
        "combat_updates": "combat_updates",
    }
    canonical = table_aliases.get(raw_table_name.strip().lower())
    if canonical is None:
        return None
    return canonical


async def _apply_flag_change(
    session,
    flag: AuditFlag,
) -> FlagApplyResult:
    supported_operations = {"create", "update", "delete", "merge"}
    supported_tables = {
        "entities",
        "quests",
        "threads",
        "events",
        "decisions",
        "loot",
        "important_quotes",
        "combat_updates",
    }
    embeddable_tables = {
        "entities",
        "quests",
        "threads",
        "events",
        "decisions",
        "loot",
        "combat_updates",
    }
    confidence_values = {"low", "medium", "high"}
    allowed_entity_types = {member.value for member in EntityType}

    embed_ids_by_table: dict[str, set[int]] = {table_name: set() for table_name in embeddable_tables}

    def _final_embed_ids() -> dict[str, list[int]]:
        return {
            table_name: sorted(record_ids)
            for table_name, record_ids in embed_ids_by_table.items()
            if record_ids
        }

    def _add_embed_id(table_name: str, record_id: int) -> None:
        if table_name in embeddable_tables:
            embed_ids_by_table[table_name].add(record_id)

    def _result(
        *,
        ok: bool,
        noop: bool,
        reason_code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> FlagApplyResult:
        return FlagApplyResult(
            ok=ok,
            noop=noop,
            reason_code=reason_code,
            message=message,
            details=details or {},
            embed_ids=_final_embed_ids(),
        )

    async def _resolve_entity_id(*, raw_entity_id: Any, raw_entity_name: Any) -> Optional[int]:
        if isinstance(raw_entity_id, int):
            existing = await session.execute(
                sa.select(Entity.id).where(Entity.id == raw_entity_id, Entity.game_id == flag.game_id)
            )
            if existing.scalar_one_or_none() is not None:
                return raw_entity_id
            return None

        if raw_entity_id is None and isinstance(raw_entity_name, str) and raw_entity_name.strip():
            existing = await session.execute(
                sa.select(Entity.id)
                .where(
                    Entity.game_id == flag.game_id,
                    Entity.name == raw_entity_name.strip(),
                )
                .limit(1)
            )
            return existing.scalar_one_or_none()
        return None

    async def _resolve_quest_id(*, raw_quest_id: Any, raw_quest_name: Any) -> Optional[int]:
        if isinstance(raw_quest_id, int):
            existing = await session.execute(
                sa.select(Quest.id).where(
                    Quest.id == raw_quest_id,
                    Quest.game_id == flag.game_id,
                    Quest.is_deleted == False,  # noqa: E712
                )
            )
            if existing.scalar_one_or_none() is not None:
                return raw_quest_id
            return None

        if raw_quest_id is None and isinstance(raw_quest_name, str) and raw_quest_name.strip():
            existing = await session.execute(
                sa.select(Quest.id)
                .where(
                    Quest.game_id == flag.game_id,
                    Quest.name == raw_quest_name.strip(),
                    Quest.is_deleted == False,  # noqa: E712
                )
                .limit(1)
            )
            return existing.scalar_one_or_none()
        return None

    async def _load_audit_note_id() -> Optional[int]:
        note_result = await session.execute(
            sa.select(AuditRun.audit_note_id).where(AuditRun.id == flag.audit_run_id)
        )
        return note_result.scalar_one_or_none()

    def _target_id_from_flag_or_change(change: dict[str, Any]) -> Optional[int]:
        if isinstance(flag.target_id, int):
            return flag.target_id
        raw_id = change.get("id")
        if isinstance(raw_id, int):
            return raw_id
        return None

    async def _row_game_id(model_cls: Any, row_id: int) -> Optional[int]:
        game_result = await session.execute(sa.select(model_cls.game_id).where(model_cls.id == row_id))
        return game_result.scalar_one_or_none()

    operation = flag.operation.strip().lower() if isinstance(flag.operation, str) else ""
    table_name = _canonicalize_audit_table_name(flag.table_name)
    confidence = flag.confidence.strip().lower() if isinstance(flag.confidence, str) else ""
    if (
        operation not in supported_operations
        or table_name not in supported_tables
        or confidence not in confidence_values
    ):
        return _result(
            ok=False,
            noop=False,
            reason_code="unsupported_operation",
            message="Unsupported operation/table_name/confidence combination",
            details={
                "operation": flag.operation,
                "table_name": flag.table_name,
                "confidence": flag.confidence,
            },
        )

    change = flag.suggested_change if isinstance(flag.suggested_change, dict) else {}
    data_payload = change.get("data") if isinstance(change.get("data"), dict) else change

    if operation == "create":
        if not isinstance(data_payload, dict):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_shape",
                message="Create operation requires suggested_change.data dict payload",
            )

        audit_note_id = await _load_audit_note_id()
        if not isinstance(audit_note_id, int):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_state",
                message="Audit run is missing audit_note_id",
                details={"audit_run_id": flag.audit_run_id},
            )

        if table_name == "entities":
            raw_name = data_payload.get("name")
            raw_entity_type = data_payload.get("entity_type")
            raw_description = data_payload.get("description")
            if (
                not isinstance(raw_name, str)
                or not raw_name.strip()
                or not isinstance(raw_entity_type, str)
                or not isinstance(raw_description, str)
            ):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Entity create requires name/entity_type/description",
                )

            name = raw_name.strip()
            entity_type = raw_entity_type.strip().lower()
            if entity_type not in allowed_entity_types:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Entity create has invalid entity_type",
                    details={"entity_type": raw_entity_type},
                )

            entity_insert_stmt = pg_insert(Entity).values(
                game_id=flag.game_id,
                entity_type=entity_type,
                name=name,
                description=raw_description,
            )
            entity_upsert_stmt = entity_insert_stmt.on_conflict_do_update(
                constraint="uq_entities_game_entity_type_name",
                set_={
                    "description": entity_insert_stmt.excluded.description,
                    "updated_at": sa.func.now(),
                },
            ).returning(Entity.id)
            entity_id = (await session.execute(entity_upsert_stmt)).scalar_one()

            await session.execute(
                pg_insert(notes_entities_table)
                .values(note_id=audit_note_id, entity_id=entity_id)
                .on_conflict_do_nothing()
            )
            _add_embed_id("entities", entity_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Entity created/upserted",
                details={"id": entity_id},
            )

        if table_name == "quests":
            raw_name = data_payload.get("name")
            raw_description = data_payload.get("description")
            raw_status = data_payload.get("status", "active")
            if (
                not isinstance(raw_name, str)
                or not raw_name.strip()
                or not isinstance(raw_description, str)
                or not isinstance(raw_status, str)
            ):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Quest create requires name/description/status",
                )

            status = raw_status.strip().lower()
            if status not in {"active", "completed"}:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Quest create has invalid status",
                    details={"status": raw_status},
                )

            quest_giver_entity_id = await _resolve_entity_id(
                raw_entity_id=data_payload.get("quest_giver_entity_id"),
                raw_entity_name=data_payload.get("entity_name") or data_payload.get("quest_giver_entity_name"),
            )

            quest_insert_stmt = pg_insert(Quest).values(
                game_id=flag.game_id,
                name=raw_name.strip(),
                description=raw_description,
                status=status,
                quest_giver_entity_id=quest_giver_entity_id,
                note_ids=[audit_note_id],
                is_deleted=False,
                deleted_at=None,
                deleted_reason=None,
            )
            quest_upsert_stmt = quest_insert_stmt.on_conflict_do_update(
                constraint="uq_quests_game_name",
                set_={
                    "description": quest_insert_stmt.excluded.description,
                    "status": quest_insert_stmt.excluded.status,
                    "quest_giver_entity_id": sa.func.coalesce(
                        quest_insert_stmt.excluded.quest_giver_entity_id,
                        Quest.quest_giver_entity_id,
                    ),
                    "note_ids": sa.func.array_append(Quest.note_ids, audit_note_id),
                    "updated_at": sa.func.now(),
                    "is_deleted": False,
                    "deleted_at": None,
                    "deleted_reason": None,
                },
            ).returning(Quest.id)
            quest_id = (await session.execute(quest_upsert_stmt)).scalar_one()
            _add_embed_id("quests", quest_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Quest created/upserted",
                details={"id": quest_id},
            )

        if table_name == "loot":
            raw_item_name = data_payload.get("item_name")
            raw_acquired_by = data_payload.get("acquired_by")
            if (
                not isinstance(raw_item_name, str)
                or not raw_item_name.strip()
                or not isinstance(raw_acquired_by, str)
                or not raw_acquired_by.strip()
            ):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Loot create requires item_name/acquired_by",
                )

            quest_id = await _resolve_quest_id(
                raw_quest_id=data_payload.get("quest_id"),
                raw_quest_name=data_payload.get("quest_name"),
            )
            loot_insert_stmt = pg_insert(Loot).values(
                game_id=flag.game_id,
                item_name=raw_item_name.strip(),
                acquired_by=raw_acquired_by.strip(),
                quest_id=quest_id,
            )
            loot_upsert_stmt = loot_insert_stmt.on_conflict_do_update(
                constraint="uq_loot_game_item_acquirer",
                set_={
                    "quest_id": sa.func.coalesce(
                        loot_insert_stmt.excluded.quest_id,
                        Loot.quest_id,
                    ),
                },
            ).returning(Loot.id)
            loot_id = (await session.execute(loot_upsert_stmt)).scalar_one()
            await session.execute(
                pg_insert(notes_loot_table)
                .values(note_id=audit_note_id, loot_id=loot_id)
                .on_conflict_do_nothing()
            )
            _add_embed_id("loot", loot_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Loot created/upserted",
                details={"id": loot_id},
            )

        if table_name == "events":
            raw_text = data_payload.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Event create requires text",
                )

            event_insert_stmt = pg_insert(Event).values(
                game_id=flag.game_id,
                text=raw_text.strip(),
            )
            event_upsert_stmt = event_insert_stmt.on_conflict_do_update(
                constraint="uq_events_game_text",
                set_={"text": event_insert_stmt.excluded.text},
            ).returning(Event.id)
            event_id = (await session.execute(event_upsert_stmt)).scalar_one()

            await session.execute(
                pg_insert(notes_events_table)
                .values(note_id=audit_note_id, event_id=event_id)
                .on_conflict_do_nothing()
            )
            _add_embed_id("events", event_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Event created/upserted",
                details={"id": event_id},
            )

        if table_name == "threads":
            raw_text = data_payload.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Thread create requires text",
                )

            quest_id = await _resolve_quest_id(
                raw_quest_id=data_payload.get("quest_id"),
                raw_quest_name=data_payload.get("quest_name"),
            )
            thread = Thread(
                game_id=flag.game_id,
                text=raw_text,
                quest_id=quest_id,
                opened_by_note_id=audit_note_id,
            )
            session.add(thread)
            await session.flush()
            if not isinstance(thread.id, int):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_state",
                    message="Thread insert did not return id",
                )
            _add_embed_id("threads", thread.id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Thread created",
                details={"id": thread.id},
            )

        if table_name == "decisions":
            raw_decision = data_payload.get("decision")
            raw_made_by = data_payload.get("made_by")
            if not isinstance(raw_decision, str) or not isinstance(raw_made_by, str):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Decision create requires decision/made_by",
                )

            decision = Decision(
                game_id=flag.game_id,
                note_id=audit_note_id,
                decision=raw_decision,
                made_by=raw_made_by,
            )
            session.add(decision)
            await session.flush()
            if not isinstance(decision.id, int):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_state",
                    message="Decision insert did not return id",
                )
            _add_embed_id("decisions", decision.id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Decision created",
                details={"id": decision.id},
            )

        if table_name == "important_quotes":
            raw_text = data_payload.get("text")
            raw_speaker = data_payload.get("speaker")
            if not isinstance(raw_text, str) or not raw_text.strip():
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Important quote create requires text",
                )
            if raw_speaker is not None and not isinstance(raw_speaker, str):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Important quote speaker must be string or null",
                )

            transcript_id: Optional[int] = None
            raw_transcript_id = data_payload.get("transcript_id")
            if isinstance(raw_transcript_id, int):
                transcript_exists = await session.execute(
                    sa.select(Transcript.id).where(
                        Transcript.id == raw_transcript_id,
                        Transcript.game_id == flag.game_id,
                    )
                )
                if transcript_exists.scalar_one_or_none() is not None:
                    transcript_id = raw_transcript_id

            quote = ImportantQuote(
                game_id=flag.game_id,
                note_id=audit_note_id,
                transcript_id=transcript_id,
                text=raw_text,
                speaker=raw_speaker,
            )
            session.add(quote)
            await session.flush()
            if not isinstance(quote.id, int):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_state",
                    message="Important quote insert did not return id",
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Important quote created",
                details={"id": quote.id},
            )

        if table_name == "combat_updates":
            raw_encounter = data_payload.get("encounter")
            raw_outcome = data_payload.get("outcome")
            if not isinstance(raw_encounter, str) or not isinstance(raw_outcome, str):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Combat update create requires encounter/outcome",
                )

            combat = CombatUpdate(
                game_id=flag.game_id,
                note_id=audit_note_id,
                encounter=raw_encounter,
                outcome=raw_outcome,
            )
            session.add(combat)
            await session.flush()
            if not isinstance(combat.id, int):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_state",
                    message="Combat update insert did not return id",
                )
            _add_embed_id("combat_updates", combat.id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Combat update created",
                details={"id": combat.id},
            )

    if operation == "update":
        target_id = _target_id_from_flag_or_change(change)
        if not isinstance(target_id, int):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_shape",
                message="Update operation requires target_id or suggested_change.id",
            )

        changes = change.get("changes")
        if not isinstance(changes, dict):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_shape",
                message="Update operation requires suggested_change.changes dict",
            )

        if table_name == "entities":
            existing = (
                await session.execute(
                    sa.select(Entity.name, Entity.entity_type).where(
                        Entity.id == target_id,
                        Entity.game_id == flag.game_id,
                    )
                )
            ).one_or_none()
            if existing is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Entity not found",
                    details={"target_id": target_id},
                )

            values: dict[str, Any] = {}
            if isinstance(changes.get("name"), str) and changes["name"].strip():
                values["name"] = changes["name"].strip()
            if isinstance(changes.get("entity_type"), str) and changes["entity_type"].strip():
                candidate_entity_type = changes["entity_type"].strip().lower()
                if candidate_entity_type not in allowed_entity_types:
                    return _result(
                        ok=False,
                        noop=False,
                        reason_code="invalid_shape",
                        message="Entity update has invalid entity_type",
                    )
                values["entity_type"] = candidate_entity_type
            if isinstance(changes.get("description"), str):
                values["description"] = changes["description"]
            if not values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Entity update has no applicable changes",
                )

            next_name = values.get("name", existing[0])
            next_entity_type = values.get("entity_type", existing[1])
            collision = await session.execute(
                sa.select(Entity.id)
                .where(
                    Entity.game_id == flag.game_id,
                    Entity.id != target_id,
                    Entity.name == next_name,
                    Entity.entity_type == next_entity_type,
                )
                .limit(1)
            )
            if collision.scalar_one_or_none() is not None:
                return _result(
                    ok=True,
                    noop=True,
                    reason_code="noop_conflict",
                    message="Entity update would violate uniqueness",
                    details={"target_id": target_id},
                )

            values["updated_at"] = sa.func.now()
            updated = await session.execute(
                sa.update(Entity)
                .where(Entity.id == target_id, Entity.game_id == flag.game_id)
                .values(**values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Entity not found",
                    details={"target_id": target_id},
                )
            _add_embed_id("entities", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Entity updated",
                details={"target_id": target_id},
            )

        if table_name == "quests":
            existing = (
                await session.execute(
                    sa.select(Quest.name, Quest.description).where(
                        Quest.id == target_id,
                        Quest.game_id == flag.game_id,
                    )
                )
            ).one_or_none()
            if existing is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Quest not found",
                    details={"target_id": target_id},
                )

            audit_note_id = await _load_audit_note_id()
            if not isinstance(audit_note_id, int):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_state",
                    message="Audit run is missing audit_note_id",
                    details={"audit_run_id": flag.audit_run_id},
                )

            quest_values: dict[str, Any] = {
                "note_ids": sa.func.array_append(Quest.note_ids, audit_note_id),
                "updated_at": sa.func.now(),
            }
            if isinstance(changes.get("name"), str) and changes["name"].strip():
                next_name = changes["name"].strip()
                collision = await session.execute(
                    sa.select(Quest.id)
                    .where(
                        Quest.game_id == flag.game_id,
                        Quest.id != target_id,
                        Quest.name == next_name,
                    )
                    .limit(1)
                )
                if collision.scalar_one_or_none() is not None:
                    return _result(
                        ok=True,
                        noop=True,
                        reason_code="noop_conflict",
                        message="Quest update would violate uniqueness",
                        details={"target_id": target_id},
                    )
                quest_values["name"] = next_name

            if isinstance(changes.get("description"), str):
                new_description = changes["description"]
                old_description = existing[1]
                if isinstance(old_description, str) and old_description != new_description:
                    session.add(
                        QuestDescriptionHistory(
                            quest_id=target_id,
                            description=old_description,
                            note_id=audit_note_id,
                        )
                    )
                quest_values["description"] = new_description

            if isinstance(changes.get("status"), str):
                next_status = changes["status"].strip().lower()
                if next_status not in {"active", "completed"}:
                    return _result(
                        ok=False,
                        noop=False,
                        reason_code="invalid_shape",
                        message="Quest update has invalid status",
                    )
                quest_values["status"] = next_status

            if "quest_giver_entity_id" in changes or "entity_name" in changes or "quest_giver_entity_name" in changes:
                if "quest_giver_entity_id" in changes and changes.get("quest_giver_entity_id") is None:
                    quest_values["quest_giver_entity_id"] = None
                else:
                    resolved_entity_id = await _resolve_entity_id(
                        raw_entity_id=changes.get("quest_giver_entity_id"),
                        raw_entity_name=changes.get("entity_name") or changes.get("quest_giver_entity_name"),
                    )
                    if resolved_entity_id is not None:
                        quest_values["quest_giver_entity_id"] = resolved_entity_id

            updated = await session.execute(
                sa.update(Quest)
                .where(Quest.id == target_id, Quest.game_id == flag.game_id)
                .values(**quest_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Quest not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("quests", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Quest updated",
                details={"target_id": target_id},
            )

        if table_name == "threads":
            if changes.get("is_resolved") is False:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Thread reopen is unsupported in update operation",
                    details={"target_id": target_id},
                )

            thread_values: dict[str, Any] = {}
            if isinstance(changes.get("text"), str):
                thread_values["text"] = changes["text"]
            if isinstance(changes.get("resolution"), str):
                thread_values["resolution"] = changes["resolution"]

            if "quest_id" in changes:
                raw_quest_id = changes.get("quest_id")
                if raw_quest_id is None:
                    thread_values["quest_id"] = None
                else:
                    resolved_quest_id = await _resolve_quest_id(
                        raw_quest_id=raw_quest_id,
                        raw_quest_name=changes.get("quest_name"),
                    )
                    if resolved_quest_id is not None:
                        thread_values["quest_id"] = resolved_quest_id
            elif "quest_name" in changes:
                resolved_quest_id = await _resolve_quest_id(
                    raw_quest_id=None,
                    raw_quest_name=changes.get("quest_name"),
                )
                if resolved_quest_id is not None:
                    thread_values["quest_id"] = resolved_quest_id

            if changes.get("is_resolved") is True:
                audit_note_id = await _load_audit_note_id()
                if not isinstance(audit_note_id, int):
                    return _result(
                        ok=False,
                        noop=False,
                        reason_code="invalid_state",
                        message="Audit run is missing audit_note_id",
                        details={"audit_run_id": flag.audit_run_id},
                    )
                thread_values["is_resolved"] = True
                thread_values["resolved_by_note_id"] = audit_note_id
                thread_values["resolved_at"] = sa.func.now()

            if not thread_values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Thread update has no applicable changes",
                )

            updated = await session.execute(
                sa.update(Thread)
                .where(
                    Thread.id == target_id,
                    Thread.game_id == flag.game_id,
                    Thread.is_deleted == False,  # noqa: E712
                )
                .values(**thread_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Thread not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("threads", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Thread updated",
                details={"target_id": target_id},
            )

        if table_name == "events":
            next_text = changes.get("text")
            if not isinstance(next_text, str):
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Event update requires text",
                )

            collision = await session.execute(
                sa.select(Event.id)
                .where(
                    Event.game_id == flag.game_id,
                    Event.id != target_id,
                    Event.text == next_text,
                )
                .limit(1)
            )
            if collision.scalar_one_or_none() is not None:
                return _result(
                    ok=True,
                    noop=True,
                    reason_code="noop_conflict",
                    message="Event update skipped due to uniqueness collision",
                    details={"target_id": target_id},
                )

            updated = await session.execute(
                sa.update(Event)
                .where(Event.id == target_id, Event.game_id == flag.game_id)
                .values(text=next_text)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Event not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("events", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Event updated",
                details={"target_id": target_id},
            )

        if table_name == "decisions":
            decision_values: dict[str, Any] = {}
            if isinstance(changes.get("decision"), str):
                decision_values["decision"] = changes["decision"]
            if isinstance(changes.get("made_by"), str):
                decision_values["made_by"] = changes["made_by"]
            if not decision_values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Decision update has no applicable changes",
                )

            updated = await session.execute(
                sa.update(Decision)
                .where(Decision.id == target_id, Decision.game_id == flag.game_id)
                .values(**decision_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Decision not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("decisions", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Decision updated",
                details={"target_id": target_id},
            )

        if table_name == "loot":
            existing = (
                await session.execute(
                    sa.select(Loot.item_name, Loot.acquired_by).where(
                        Loot.id == target_id,
                        Loot.game_id == flag.game_id,
                    )
                )
            ).one_or_none()
            if existing is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Loot not found",
                    details={"target_id": target_id},
                )

            loot_values: dict[str, Any] = {}
            if isinstance(changes.get("item_name"), str) and changes["item_name"].strip():
                loot_values["item_name"] = changes["item_name"].strip()
            if isinstance(changes.get("acquired_by"), str) and changes["acquired_by"].strip():
                loot_values["acquired_by"] = changes["acquired_by"].strip()

            if "quest_id" in changes:
                raw_quest_id = changes.get("quest_id")
                if raw_quest_id is None:
                    loot_values["quest_id"] = None
                else:
                    resolved_quest_id = await _resolve_quest_id(
                        raw_quest_id=raw_quest_id,
                        raw_quest_name=changes.get("quest_name"),
                    )
                    if resolved_quest_id is not None:
                        loot_values["quest_id"] = resolved_quest_id
            elif "quest_name" in changes:
                resolved_quest_id = await _resolve_quest_id(
                    raw_quest_id=None,
                    raw_quest_name=changes.get("quest_name"),
                )
                if resolved_quest_id is not None:
                    loot_values["quest_id"] = resolved_quest_id

            if not loot_values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Loot update has no applicable changes",
                )

            next_item_name = loot_values.get("item_name", existing[0])
            next_acquired_by = loot_values.get("acquired_by", existing[1])
            collision = await session.execute(
                sa.select(Loot.id)
                .where(
                    Loot.game_id == flag.game_id,
                    Loot.id != target_id,
                    Loot.item_name == next_item_name,
                    Loot.acquired_by == next_acquired_by,
                )
                .limit(1)
            )
            if collision.scalar_one_or_none() is not None:
                return _result(
                    ok=True,
                    noop=True,
                    reason_code="noop_conflict",
                    message="Loot update skipped due to uniqueness collision",
                    details={"target_id": target_id},
                )

            updated = await session.execute(
                sa.update(Loot)
                .where(Loot.id == target_id, Loot.game_id == flag.game_id)
                .values(**loot_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Loot not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("loot", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Loot updated",
                details={"target_id": target_id},
            )

        if table_name == "important_quotes":
            quote_values: dict[str, Any] = {}
            if isinstance(changes.get("text"), str):
                quote_values["text"] = changes["text"]
            if "speaker" in changes and (
                changes.get("speaker") is None or isinstance(changes.get("speaker"), str)
            ):
                quote_values["speaker"] = changes.get("speaker")
            if "transcript_id" in changes:
                raw_transcript_id = changes.get("transcript_id")
                if raw_transcript_id is None:
                    quote_values["transcript_id"] = None
                elif isinstance(raw_transcript_id, int):
                    transcript_exists = await session.execute(
                        sa.select(Transcript.id).where(
                            Transcript.id == raw_transcript_id,
                            Transcript.game_id == flag.game_id,
                        )
                    )
                    if transcript_exists.scalar_one_or_none() is not None:
                        quote_values["transcript_id"] = raw_transcript_id

            if not quote_values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Important quote update has no applicable changes",
                )

            updated = await session.execute(
                sa.update(ImportantQuote)
                .where(ImportantQuote.id == target_id, ImportantQuote.game_id == flag.game_id)
                .values(**quote_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Important quote not found",
                    details={"target_id": target_id},
                )

            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Important quote updated",
                details={"target_id": target_id},
            )

        if table_name == "combat_updates":
            combat_values: dict[str, Any] = {}
            if isinstance(changes.get("encounter"), str):
                combat_values["encounter"] = changes["encounter"]
            if isinstance(changes.get("outcome"), str):
                combat_values["outcome"] = changes["outcome"]
            if not combat_values:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="invalid_shape",
                    message="Combat update has no applicable changes",
                )

            updated = await session.execute(
                sa.update(CombatUpdate)
                .where(CombatUpdate.id == target_id, CombatUpdate.game_id == flag.game_id)
                .values(**combat_values)
            )
            if _affected_rows(updated) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Combat update not found",
                    details={"target_id": target_id},
                )

            _add_embed_id("combat_updates", target_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Combat update modified",
                details={"target_id": target_id},
            )

    if operation == "delete":
        target_id = _target_id_from_flag_or_change(change)
        if not isinstance(target_id, int):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_shape",
                message="Delete operation requires target_id or suggested_change.id",
            )

        reason = change.get("reason")
        delete_reason = (
            reason.strip()
            if isinstance(reason, str) and reason.strip()
            else "audit flag deletion candidate"
        )

        if table_name == "quests":
            existing = await session.execute(
                sa.select(Quest.is_deleted).where(Quest.id == target_id, Quest.game_id == flag.game_id)
            )
            is_deleted = existing.scalar_one_or_none()
            if is_deleted is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Quest not found",
                    details={"target_id": target_id},
                )
            if is_deleted:
                return _result(
                    ok=True,
                    noop=True,
                    reason_code="already_deleted",
                    message="Quest already soft-deleted",
                    details={"target_id": target_id},
                )

            await session.execute(
                sa.update(Quest)
                .where(Quest.id == target_id, Quest.game_id == flag.game_id)
                .values(
                    is_deleted=True,
                    deleted_at=sa.func.now(),
                    deleted_reason=delete_reason,
                    updated_at=sa.func.now(),
                )
            )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Quest soft-deleted",
                details={"target_id": target_id},
            )

        if table_name == "threads":
            existing = await session.execute(
                sa.select(Thread.is_deleted).where(Thread.id == target_id, Thread.game_id == flag.game_id)
            )
            is_deleted = existing.scalar_one_or_none()
            if is_deleted is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Thread not found",
                    details={"target_id": target_id},
                )
            if is_deleted:
                return _result(
                    ok=True,
                    noop=True,
                    reason_code="already_deleted",
                    message="Thread already soft-deleted",
                    details={"target_id": target_id},
                )

            await session.execute(
                sa.update(Thread)
                .where(Thread.id == target_id, Thread.game_id == flag.game_id)
                .values(
                    is_deleted=True,
                    deleted_at=sa.func.now(),
                    deleted_reason=delete_reason,
                )
            )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Thread soft-deleted",
                details={"target_id": target_id},
            )

        if table_name == "entities":
            entity = await session.get(Entity, target_id)
            if entity is None or entity.game_id != flag.game_id:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Entity not found",
                    details={"target_id": target_id},
                )

            await session.execute(
                sa.update(Quest)
                .where(Quest.game_id == flag.game_id, Quest.quest_giver_entity_id == target_id)
                .values(quest_giver_entity_id=None, updated_at=sa.func.now())
            )
            await session.execute(
                sa.delete(notes_entities_table).where(notes_entities_table.c.entity_id == target_id)
            )
            deleted = await session.execute(
                sa.delete(Entity).where(Entity.id == target_id, Entity.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Entity not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Entity hard-deleted",
                details={"target_id": target_id},
            )

        if table_name == "events":
            await session.execute(
                sa.delete(notes_events_table).where(notes_events_table.c.event_id == target_id)
            )
            deleted = await session.execute(
                sa.delete(Event).where(Event.id == target_id, Event.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Event not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Event hard-deleted",
                details={"target_id": target_id},
            )

        if table_name == "loot":
            await session.execute(
                sa.delete(notes_loot_table).where(notes_loot_table.c.loot_id == target_id)
            )
            deleted = await session.execute(
                sa.delete(Loot).where(Loot.id == target_id, Loot.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Loot not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Loot hard-deleted",
                details={"target_id": target_id},
            )

        if table_name == "decisions":
            deleted = await session.execute(
                sa.delete(Decision).where(Decision.id == target_id, Decision.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Decision not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Decision hard-deleted",
                details={"target_id": target_id},
            )

        if table_name == "important_quotes":
            deleted = await session.execute(
                sa.delete(ImportantQuote).where(
                    ImportantQuote.id == target_id,
                    ImportantQuote.game_id == flag.game_id,
                )
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Important quote not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Important quote hard-deleted",
                details={"target_id": target_id},
            )

        if table_name == "combat_updates":
            deleted = await session.execute(
                sa.delete(CombatUpdate).where(
                    CombatUpdate.id == target_id,
                    CombatUpdate.game_id == flag.game_id,
                )
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Combat update not found",
                    details={"target_id": target_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Combat update hard-deleted",
                details={"target_id": target_id},
            )

    if operation == "merge":
        canonical_id = change.get("canonical_id")
        duplicate_id = change.get("duplicate_id")
        if not isinstance(canonical_id, int) or not isinstance(duplicate_id, int):
            return _result(
                ok=False,
                noop=False,
                reason_code="invalid_shape",
                message="Merge operation requires canonical_id and duplicate_id",
            )
        if canonical_id == duplicate_id:
            return _result(
                ok=True,
                noop=True,
                reason_code="noop_same_record",
                message="Merge canonical_id and duplicate_id are identical",
                details={"canonical_id": canonical_id},
            )

        model_map = {
            "entities": Entity,
            "quests": Quest,
            "threads": Thread,
            "events": Event,
            "decisions": Decision,
            "loot": Loot,
            "important_quotes": ImportantQuote,
            "combat_updates": CombatUpdate,
        }
        model_cls = model_map[table_name]
        canonical_game_id = await _row_game_id(model_cls, canonical_id)
        duplicate_game_id = await _row_game_id(model_cls, duplicate_id)
        if canonical_game_id is None or duplicate_game_id is None:
            return _result(
                ok=False,
                noop=False,
                reason_code="not_found",
                message="Merge canonical or duplicate row not found",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )
        if canonical_game_id != flag.game_id or duplicate_game_id != flag.game_id:
            return _result(
                ok=False,
                noop=False,
                reason_code="cross_game",
                message="Merge rows do not belong to flag game",
                details={
                    "canonical_game_id": canonical_game_id,
                    "duplicate_game_id": duplicate_game_id,
                    "flag_game_id": flag.game_id,
                },
            )

        if table_name == "entities":
            duplicate_note_rows = await session.execute(
                sa.select(notes_entities_table.c.note_id).where(notes_entities_table.c.entity_id == duplicate_id)
            )
            for note_id in [row[0] for row in duplicate_note_rows.all()]:
                await session.execute(
                    pg_insert(notes_entities_table)
                    .values(note_id=note_id, entity_id=canonical_id)
                    .on_conflict_do_nothing()
                )

            await session.execute(
                sa.update(Quest)
                .where(Quest.game_id == flag.game_id, Quest.quest_giver_entity_id == duplicate_id)
                .values(quest_giver_entity_id=canonical_id, updated_at=sa.func.now())
            )
            await session.execute(
                sa.delete(notes_entities_table).where(notes_entities_table.c.entity_id == duplicate_id)
            )
            deleted = await session.execute(
                sa.delete(Entity).where(Entity.id == duplicate_id, Entity.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate entity not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("entities", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Entity merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "quests":
            canonical_notes = (
                await session.execute(sa.select(Quest.note_ids).where(Quest.id == canonical_id))
            ).scalar_one_or_none()
            duplicate_notes = (
                await session.execute(sa.select(Quest.note_ids).where(Quest.id == duplicate_id))
            ).scalar_one_or_none()
            if canonical_notes is None or duplicate_notes is None:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Merge canonical or duplicate quest not found",
                )

            merged_note_ids: list[int] = []
            seen_note_ids: set[int] = set()
            for note_id in [*(canonical_notes or []), *(duplicate_notes or [])]:
                if isinstance(note_id, int) and note_id not in seen_note_ids:
                    seen_note_ids.add(note_id)
                    merged_note_ids.append(note_id)

            await session.execute(
                sa.update(Quest)
                .where(Quest.id == canonical_id, Quest.game_id == flag.game_id)
                .values(note_ids=merged_note_ids, updated_at=sa.func.now())
            )
            await session.execute(
                sa.update(Thread)
                .where(Thread.game_id == flag.game_id, Thread.quest_id == duplicate_id)
                .values(quest_id=canonical_id)
            )
            await session.execute(
                sa.update(Loot)
                .where(Loot.game_id == flag.game_id, Loot.quest_id == duplicate_id)
                .values(quest_id=canonical_id)
            )
            deleted = await session.execute(
                sa.delete(Quest).where(Quest.id == duplicate_id, Quest.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate quest not found",
                    details={"duplicate_id": duplicate_id},
                )

            _add_embed_id("quests", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Quest merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "events":
            duplicate_note_rows = await session.execute(
                sa.select(notes_events_table.c.note_id).where(notes_events_table.c.event_id == duplicate_id)
            )
            for note_id in [row[0] for row in duplicate_note_rows.all()]:
                await session.execute(
                    pg_insert(notes_events_table)
                    .values(note_id=note_id, event_id=canonical_id)
                    .on_conflict_do_nothing()
                )
            await session.execute(
                sa.delete(notes_events_table).where(notes_events_table.c.event_id == duplicate_id)
            )
            deleted = await session.execute(
                sa.delete(Event).where(Event.id == duplicate_id, Event.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate event not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("events", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Event merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "loot":
            duplicate_note_rows = await session.execute(
                sa.select(notes_loot_table.c.note_id).where(notes_loot_table.c.loot_id == duplicate_id)
            )
            for note_id in [row[0] for row in duplicate_note_rows.all()]:
                await session.execute(
                    pg_insert(notes_loot_table)
                    .values(note_id=note_id, loot_id=canonical_id)
                    .on_conflict_do_nothing()
                )
            await session.execute(
                sa.delete(notes_loot_table).where(notes_loot_table.c.loot_id == duplicate_id)
            )
            deleted = await session.execute(
                sa.delete(Loot).where(Loot.id == duplicate_id, Loot.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate loot not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("loot", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Loot merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "threads":
            deleted = await session.execute(
                sa.delete(Thread).where(Thread.id == duplicate_id, Thread.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate thread not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("threads", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Thread merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "decisions":
            deleted = await session.execute(
                sa.delete(Decision).where(Decision.id == duplicate_id, Decision.game_id == flag.game_id)
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate decision not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("decisions", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Decision merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "important_quotes":
            deleted = await session.execute(
                sa.delete(ImportantQuote).where(
                    ImportantQuote.id == duplicate_id,
                    ImportantQuote.game_id == flag.game_id,
                )
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate important quote not found",
                    details={"duplicate_id": duplicate_id},
                )
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Important quote merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

        if table_name == "combat_updates":
            deleted = await session.execute(
                sa.delete(CombatUpdate).where(
                    CombatUpdate.id == duplicate_id,
                    CombatUpdate.game_id == flag.game_id,
                )
            )
            if _affected_rows(deleted) == 0:
                return _result(
                    ok=False,
                    noop=False,
                    reason_code="not_found",
                    message="Duplicate combat update not found",
                    details={"duplicate_id": duplicate_id},
                )
            _add_embed_id("combat_updates", canonical_id)
            return _result(
                ok=True,
                noop=False,
                reason_code="applied",
                message="Combat update merged",
                details={"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )

    return _result(
        ok=False,
        noop=False,
        reason_code="unsupported_operation",
        message="Unsupported operation/table_name combination",
        details={"operation": operation, "table_name": table_name},
    )


async def apply_audit_flag(flag_id: int) -> AuditFlagMutationResult:
    """Apply an audit flag action with idempotent status semantics."""
    embed_ids: dict[str, list[int]] = {}
    mutation_result: Optional[AuditFlagMutationResult] = None

    async with AsyncSessionLocal() as session:
        async with session.begin():
            flag_result = await session.execute(
                sa.select(AuditFlag).where(AuditFlag.id == flag_id).with_for_update()
            )
            flag = flag_result.scalar_one_or_none()
            if flag is None:
                return _flag_result(
                    flag_id=flag_id,
                    ok=False,
                    noop=False,
                    status=None,
                    reason_code="not_found",
                    message="Audit flag not found",
                )

            if flag.status == "applied":
                return _flag_result(
                    flag_id=flag.id,
                    ok=True,
                    noop=True,
                    status=flag.status,
                    reason_code="already_applied",
                    message="Audit flag already applied",
                )

            if flag.status != "pending":
                return _flag_result(
                    flag_id=flag.id,
                    ok=False,
                    noop=False,
                    status=flag.status,
                    reason_code="invalid_transition",
                    message="Flag must be pending before apply",
                )

            apply_result = await _apply_flag_change(session, flag)
            if not apply_result.ok:
                return _flag_result(
                    flag_id=flag.id,
                    ok=False,
                    noop=apply_result.noop,
                    status=flag.status,
                    reason_code=apply_result.reason_code,
                    message=apply_result.message,
                    details=apply_result.details,
                )

            await session.execute(
                sa.update(AuditFlag)
                .where(AuditFlag.id == flag.id)
                .values(status="applied", resolved_at=sa.func.now())
            )

            embed_ids = apply_result.embed_ids
            mutation_result = _flag_result(
                flag_id=flag.id,
                ok=True,
                noop=apply_result.noop,
                status="applied",
                reason_code=apply_result.reason_code,
                message=apply_result.message,
                details=apply_result.details,
            )

    assert mutation_result is not None
    if mutation_result.ok and not mutation_result.noop and embed_ids:
        asyncio.create_task(_write_flag_embeddings(embed_ids))
    return mutation_result


async def dismiss_audit_flag(flag_id: int) -> AuditFlagMutationResult:
    """Dismiss an audit flag with idempotent status semantics."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            flag_result = await session.execute(
                sa.select(AuditFlag).where(AuditFlag.id == flag_id).with_for_update()
            )
            flag = flag_result.scalar_one_or_none()
            if flag is None:
                return _flag_result(
                    flag_id=flag_id,
                    ok=False,
                    noop=False,
                    status=None,
                    reason_code="not_found",
                    message="Audit flag not found",
                )

            if flag.status == "dismissed":
                return _flag_result(
                    flag_id=flag.id,
                    ok=True,
                    noop=True,
                    status=flag.status,
                    reason_code="already_dismissed",
                    message="Audit flag already dismissed",
                )

            if flag.status != "pending":
                return _flag_result(
                    flag_id=flag.id,
                    ok=False,
                    noop=False,
                    status=flag.status,
                    reason_code="invalid_transition",
                    message="Flag must be pending before dismiss",
                )

            await session.execute(
                sa.update(AuditFlag)
                .where(AuditFlag.id == flag.id)
                .values(status="dismissed", resolved_at=sa.func.now())
            )
            return _flag_result(
                flag_id=flag.id,
                ok=True,
                noop=False,
                status="dismissed",
                reason_code="dismissed",
                message="Audit flag dismissed",
            )


async def reopen_audit_flag(flag_id: int) -> AuditFlagMutationResult:
    """Reopen a previously resolved audit flag."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            flag_result = await session.execute(
                sa.select(AuditFlag).where(AuditFlag.id == flag_id).with_for_update()
            )
            flag = flag_result.scalar_one_or_none()
            if flag is None:
                return _flag_result(
                    flag_id=flag_id,
                    ok=False,
                    noop=False,
                    status=None,
                    reason_code="not_found",
                    message="Audit flag not found",
                )

            if flag.status == "pending":
                return _flag_result(
                    flag_id=flag.id,
                    ok=True,
                    noop=True,
                    status=flag.status,
                    reason_code="already_pending",
                    message="Audit flag already pending",
                )

            await session.execute(
                sa.update(AuditFlag)
                .where(AuditFlag.id == flag.id)
                .values(status="pending", resolved_at=None)
            )
            return _flag_result(
                flag_id=flag.id,
                ok=True,
                noop=False,
                status="pending",
                reason_code="reopened",
                message="Audit flag reopened",
            )


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
                    await session.execute(
                        pg_insert(notes_entities_table)
                        .values(note_id=note_id, entity_id=entity_id)
                        .on_conflict_do_nothing()
                    )

            # 3. Resolve quest giver entity names to IDs
            # If a quest references a giver by name (quest_giver_entity_name) but not by ID,
            # try to find the matching NPC entity and populate the ID.
            async def resolve_quest_giver(q: dict) -> None:
                """Resolve quest_giver_entity_name to quest_giver_entity_id if needed."""
                if (
                    q.get("quest_giver_entity_id") is None
                    and q.get("quest_giver_entity_name") is not None
                ):
                    giver_name = q["quest_giver_entity_name"]
                    # Look up the NPC entity by name in the same game
                    giver_result = await session.execute(
                        sa.select(Entity.id).where(
                            Entity.game_id == game_id,
                            Entity.entity_type == EntityType.npc,
                            Entity.name == giver_name,
                        )
                    )
                    giver_id = giver_result.scalar()
                    if giver_id is not None:
                        q["quest_giver_entity_id"] = giver_id
                    else:
                        # Entity with that name doesn't exist; nullify and log
                        logger.warning(
                            "Quest '%s' references missing or non-NPC giver entity '%s'; dropping reference",
                            q.get("name", "unknown"),
                            giver_name,
                            extra={"game_id": game_id},
                        )
                        q["quest_giver_entity_name"] = None

            # Resolve giver names for all quests_opened
            for q in quests_opened:
                await resolve_quest_giver(q)

            # Also resolve for quests_updated
            for q in quests_updated:
                await resolve_quest_giver(q)

            # 4. Upsert quests from quests_opened (new active quests)
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

            # 5. Mark quests as completed
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

            # 6. Upsert quests_updated (partial updates to existing quests)
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

            # 7. Create new threads; collect IDs via flush
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
                new_thread = Thread(game_id=game_id, text=text, quest_id=safe_quest_id, opened_by_note_id=note_id)
                session.add(new_thread)
                await session.flush()
                inserted_thread_ids.append(new_thread.id)

            # 8. Resolve threads (three-tier validation: missing / cross-game / already resolved)
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

            # 9. Insert decisions; collect IDs via flush
            for d in decisions:
                d_obj = Decision(
                    game_id=game_id, note_id=note_id,
                    decision=d["decision"], made_by=d["made_by"],
                )
                session.add(d_obj)
                await session.flush()
                inserted_decision_ids.append(d_obj.id)

            # 10. Upsert events + m2m link to note; collect IDs
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

            # 11. Upsert loot + m2m link to note; collect IDs
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

            # 12. Insert combat_updates; collect IDs via flush
            for c in combat_updates:
                c_obj = CombatUpdate(
                    game_id=game_id, note_id=note_id,
                    encounter=c["encounter"], outcome=c["outcome"],
                )
                session.add(c_obj)
                await session.flush()
                inserted_combat_ids.append(c_obj.id)

            # 13. Insert important_quotes (validate transcript_id against current batch)
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

            # 14. Mark all source transcripts as processed
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


async def write_audit_pipeline_result(
    *,
    game_id: int,
    audit_run_id: int,
    output: Any,
    notes: list[Note],
) -> AuditPipelineResult:
    """Persist audit pipeline output with split transactions for failure safety.

    Step 1 creates a synthetic audit note in its own transaction.
    Step 2 applies all corrections/creations/flags/finalization atomically.
    """
    output_payload = _model_to_dict(output)
    table_order: tuple[str, ...] = (
        "entities",
        "quests",
        "threads",
        "events",
        "decisions",
        "loot",
        "important_quotes",
        "combat_updates",
    )

    table_changesets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for table_name in table_order:
        raw_changeset = output_payload.get(table_name)
        changeset_payload: dict[str, Any] = {}
        if raw_changeset is not None:
            try:
                changeset_payload = _model_to_dict(raw_changeset)
            except TypeError:
                logger.warning(
                    "Audit output table '%s' is malformed; using empty changeset",
                    table_name,
                )
        table_changesets[table_name] = {
            "creates": _model_list_to_dicts(changeset_payload.get("creates")),
            "updates": _model_list_to_dicts(changeset_payload.get("updates")),
            "deletes": _model_list_to_dicts(changeset_payload.get("deletes")),
            "merges": _model_list_to_dicts(changeset_payload.get("merges")),
        }

    note_ids_audited = sorted({n.id for n in notes})
    min_note_id = min(note_ids_audited) if note_ids_audited else None
    max_note_id = max(note_ids_audited) if note_ids_audited else None

    source_transcript_ids: list[int] = []
    seen_transcript_ids: set[int] = set()
    for note in notes:
        for tid in note.source_transcript_ids or []:
            if tid not in seen_transcript_ids:
                seen_transcript_ids.add(tid)
                source_transcript_ids.append(tid)

    audit_note_summary = (
        f"Audit correction pass for {len(note_ids_audited)} note(s)"
        if note_ids_audited
        else "Audit correction pass (no source notes)"
    )

    # Step 1: own transaction, create synthetic audit note.
    audit_note_id: Optional[int] = None
    async with AsyncSessionLocal() as session:
        async with session.begin():
            audit_note = Note(
                game_id=game_id,
                summary=audit_note_summary,
                source_transcript_ids=source_transcript_ids,
                is_audit=True,
            )
            session.add(audit_note)
            await session.flush()
            audit_note_id = audit_note.id

    assert audit_note_id is not None

    entity_ids_to_embed: set[int] = set()
    thread_ids_to_embed: set[int] = set()
    event_ids_to_embed: set[int] = set()
    decision_ids_to_embed: set[int] = set()
    loot_ids_to_embed: set[int] = set()
    quest_ids_to_embed: set[int] = set()
    combat_ids_to_embed: set[int] = set()

    try:
        # Step 2+: single atomic transaction.
        async with AsyncSessionLocal() as session:
            async with session.begin():
                snapshot_fields_by_table: dict[str, tuple[str, ...]] = {
                    "entities": ("id", "name", "entity_type", "description"),
                    "quests": ("id", "name", "description", "status", "quest_giver_entity_id"),
                    "threads": ("id", "text", "is_resolved", "resolution", "quest_id"),
                    "events": ("id", "text"),
                    "decisions": ("id", "decision", "made_by"),
                    "loot": ("id", "item_name", "acquired_by", "quest_id"),
                    "important_quotes": ("id", "text", "speaker", "transcript_id"),
                    "combat_updates": ("id", "encounter", "outcome"),
                }
                table_model_by_name: dict[str, Any] = {
                    "entities": Entity,
                    "quests": Quest,
                    "threads": Thread,
                    "events": Event,
                    "decisions": Decision,
                    "loot": Loot,
                    "important_quotes": ImportantQuote,
                    "combat_updates": CombatUpdate,
                }
                allowed_entity_types = {member.value for member in EntityType}

                entity_name_to_id: dict[str, int] = {}
                quest_name_to_id: dict[str, int] = {}

                def _normalize_name(value: Any) -> Optional[str]:
                    if not isinstance(value, str):
                        return None
                    normalized = value.strip().lower()
                    return normalized if normalized else None

                def _coerce_dict(value: Any, *, fallback_label: str) -> dict[str, Any]:
                    if isinstance(value, dict):
                        return dict(value)
                    if value is None:
                        return {}
                    try:
                        return _model_to_dict(value)
                    except TypeError:
                        logger.warning("Skipping malformed %s payload: %s", fallback_label, value)
                        return {}

                def _normalize_confidence(op: dict[str, Any], *, context: str) -> str:
                    raw = op.get("confidence")
                    if isinstance(raw, str):
                        normalized = raw.strip().lower()
                        if normalized in {"low", "medium", "high"}:
                            return normalized
                    logger.warning(
                        "Malformed confidence in %s; defaulting to 'medium': %s",
                        context,
                        op,
                    )
                    return "medium"

                def _normalize_description(op: dict[str, Any], *, fallback: str) -> str:
                    raw = op.get("description")
                    if isinstance(raw, str):
                        text = raw.strip()
                        if text:
                            return text
                    return fallback

                def _track_embedding_id(table_name: str, record_id: int) -> None:
                    if table_name == "entities":
                        entity_ids_to_embed.add(record_id)
                    elif table_name == "threads":
                        thread_ids_to_embed.add(record_id)
                    elif table_name == "events":
                        event_ids_to_embed.add(record_id)
                    elif table_name == "decisions":
                        decision_ids_to_embed.add(record_id)
                    elif table_name == "loot":
                        loot_ids_to_embed.add(record_id)
                    elif table_name == "quests":
                        quest_ids_to_embed.add(record_id)
                    elif table_name == "combat_updates":
                        combat_ids_to_embed.add(record_id)

                async def _load_snapshot(table_name: str, record_id: int) -> Optional[dict[str, Any]]:
                    model_cls = table_model_by_name[table_name]
                    fields = snapshot_fields_by_table[table_name]
                    columns = [getattr(model_cls, field_name) for field_name in fields]
                    result = await session.execute(
                        sa.select(*columns)
                        .where(
                            model_cls.id == record_id,
                            model_cls.game_id == game_id,
                        )
                        .limit(1)
                    )
                    row = result.one_or_none()
                    if row is None:
                        return None
                    return {field_name: row[idx] for idx, field_name in enumerate(fields)}

                async def _resolve_entity_reference(
                    *,
                    raw_entity_id: Any,
                    raw_entity_name: Any,
                ) -> Optional[int]:
                    if isinstance(raw_entity_id, int):
                        existing = await session.execute(
                            sa.select(Entity.id).where(Entity.id == raw_entity_id, Entity.game_id == game_id)
                        )
                        if existing.scalar_one_or_none() is not None:
                            return raw_entity_id
                        logger.warning(
                            "Ignoring quest_giver_entity_id=%s not found in game_id=%d",
                            raw_entity_id,
                            game_id,
                        )
                        return None
                    if raw_entity_id is None:
                        normalized_name = _normalize_name(raw_entity_name)
                        if normalized_name is not None:
                            return entity_name_to_id.get(normalized_name)
                    return None

                async def _resolve_quest_reference(
                    *,
                    raw_quest_id: Any,
                    raw_quest_name: Any,
                ) -> Optional[int]:
                    if isinstance(raw_quest_id, int):
                        existing = await session.execute(
                            sa.select(Quest.id).where(
                                Quest.id == raw_quest_id,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            return raw_quest_id
                        logger.warning(
                            "Ignoring quest_id=%s not found/active in game_id=%d",
                            raw_quest_id,
                            game_id,
                        )
                        return None
                    if raw_quest_id is None:
                        normalized_name = _normalize_name(raw_quest_name)
                        if normalized_name is not None:
                            return quest_name_to_id.get(normalized_name)
                    return None

                def _append_flag(
                    *,
                    operation: str,
                    table_name: str,
                    confidence: str,
                    target_id: Optional[int],
                    description: str,
                    suggested_change: dict[str, Any],
                    status: str,
                ) -> None:
                    resolved_at = datetime.now(timezone.utc) if status == "applied" else None
                    session.add(
                        AuditFlag(
                            game_id=game_id,
                            audit_run_id=audit_run_id,
                            operation=operation,
                            table_name=table_name,
                            confidence=confidence,
                            target_id=target_id,
                            description=description,
                            suggested_change=suggested_change,
                            status=status,
                            resolved_at=resolved_at,
                        )
                    )

                async def _apply_create(
                    table_name: str,
                    data: dict[str, Any],
                ) -> tuple[bool, Optional[int], Optional[dict[str, Any]]]:
                    if table_name == "entities":
                        raw_name = data.get("name")
                        raw_entity_type = data.get("entity_type")
                        raw_description = data.get("description")
                        if not isinstance(raw_name, str) or not raw_name.strip():
                            return False, None, None
                        if not isinstance(raw_entity_type, str):
                            return False, None, None
                        if not isinstance(raw_description, str):
                            return False, None, None

                        name = raw_name.strip()
                        entity_type = raw_entity_type.strip().lower()
                        if entity_type not in allowed_entity_types:
                            logger.warning("Skipping entity create with invalid entity_type: %s", data)
                            return False, None, None

                        entity_insert_stmt = pg_insert(Entity).values(
                            game_id=game_id,
                            entity_type=entity_type,
                            name=name,
                            description=raw_description,
                        )
                        entity_upsert_stmt = entity_insert_stmt.on_conflict_do_update(
                            constraint="uq_entities_game_entity_type_name",
                            set_={
                                "description": entity_insert_stmt.excluded.description,
                                "updated_at": sa.func.now(),
                            },
                        ).returning(Entity.id)
                        entity_id = (await session.execute(entity_upsert_stmt)).scalar_one()
                        await session.execute(
                            pg_insert(notes_entities_table)
                            .values(note_id=audit_note_id, entity_id=entity_id)
                            .on_conflict_do_nothing()
                        )
                        _track_embedding_id("entities", entity_id)
                        after = await _load_snapshot("entities", entity_id)
                        return after is not None, entity_id, after

                    if table_name == "quests":
                        raw_name = data.get("name")
                        raw_description = data.get("description")
                        raw_status = data.get("status", "active")
                        if not isinstance(raw_name, str) or not raw_name.strip():
                            return False, None, None
                        if not isinstance(raw_description, str):
                            return False, None, None
                        if not isinstance(raw_status, str):
                            return False, None, None

                        status = raw_status.strip().lower()
                        if status not in {"active", "completed"}:
                            return False, None, None

                        quest_giver_entity_id = await _resolve_entity_reference(
                            raw_entity_id=data.get("quest_giver_entity_id"),
                            raw_entity_name=data.get("entity_name"),
                        )

                        quest_insert_stmt = pg_insert(Quest).values(
                            game_id=game_id,
                            name=raw_name.strip(),
                            description=raw_description,
                            status=status,
                            quest_giver_entity_id=quest_giver_entity_id,
                            note_ids=[audit_note_id],
                            is_deleted=False,
                            deleted_at=None,
                            deleted_reason=None,
                        )
                        quest_upsert_stmt = quest_insert_stmt.on_conflict_do_update(
                            constraint="uq_quests_game_name",
                            set_={
                                "description": quest_insert_stmt.excluded.description,
                                "status": quest_insert_stmt.excluded.status,
                                "quest_giver_entity_id": sa.func.coalesce(
                                    quest_insert_stmt.excluded.quest_giver_entity_id,
                                    Quest.quest_giver_entity_id,
                                ),
                                "note_ids": sa.func.array_append(Quest.note_ids, audit_note_id),
                                "updated_at": sa.func.now(),
                                "is_deleted": False,
                                "deleted_at": None,
                                "deleted_reason": None,
                            },
                        ).returning(Quest.id)
                        quest_id = (await session.execute(quest_upsert_stmt)).scalar_one()
                        _track_embedding_id("quests", quest_id)
                        after = await _load_snapshot("quests", quest_id)
                        return after is not None, quest_id, after

                    if table_name == "threads":
                        raw_text = data.get("text")
                        if not isinstance(raw_text, str) or not raw_text.strip():
                            return False, None, None

                        safe_quest_id = await _resolve_quest_reference(
                            raw_quest_id=data.get("quest_id"),
                            raw_quest_name=data.get("quest_name"),
                        )
                        thread = Thread(
                            game_id=game_id,
                            text=raw_text,
                            quest_id=safe_quest_id,
                            opened_by_note_id=audit_note_id,
                        )
                        session.add(thread)
                        await session.flush()
                        thread_id = thread.id
                        if thread_id is None:
                            return False, None, None
                        _track_embedding_id("threads", thread_id)
                        after = await _load_snapshot("threads", thread_id)
                        return after is not None, thread_id, after

                    if table_name == "loot":
                        raw_item_name = data.get("item_name")
                        raw_acquired_by = data.get("acquired_by")
                        if not isinstance(raw_item_name, str) or not raw_item_name.strip():
                            return False, None, None
                        if not isinstance(raw_acquired_by, str) or not raw_acquired_by.strip():
                            return False, None, None

                        safe_quest_id = await _resolve_quest_reference(
                            raw_quest_id=data.get("quest_id"),
                            raw_quest_name=data.get("quest_name"),
                        )
                        loot_insert_stmt = pg_insert(Loot).values(
                            game_id=game_id,
                            item_name=raw_item_name.strip(),
                            acquired_by=raw_acquired_by.strip(),
                            quest_id=safe_quest_id,
                        )
                        loot_upsert_stmt = loot_insert_stmt.on_conflict_do_update(
                            constraint="uq_loot_game_item_acquirer",
                            set_={
                                "quest_id": sa.func.coalesce(
                                    loot_insert_stmt.excluded.quest_id,
                                    Loot.quest_id,
                                ),
                            },
                        ).returning(Loot.id)
                        loot_id = (await session.execute(loot_upsert_stmt)).scalar_one()
                        await session.execute(
                            pg_insert(notes_loot_table)
                            .values(note_id=audit_note_id, loot_id=loot_id)
                            .on_conflict_do_nothing()
                        )
                        _track_embedding_id("loot", loot_id)
                        after = await _load_snapshot("loot", loot_id)
                        return after is not None, loot_id, after

                    if table_name == "decisions":
                        raw_decision = data.get("decision")
                        raw_made_by = data.get("made_by")
                        if not isinstance(raw_decision, str) or not isinstance(raw_made_by, str):
                            return False, None, None
                        decision = Decision(
                            game_id=game_id,
                            note_id=audit_note_id,
                            decision=raw_decision,
                            made_by=raw_made_by,
                        )
                        session.add(decision)
                        await session.flush()
                        decision_id = decision.id
                        if decision_id is None:
                            return False, None, None
                        _track_embedding_id("decisions", decision_id)
                        after = await _load_snapshot("decisions", decision_id)
                        return after is not None, decision_id, after

                    if table_name == "important_quotes":
                        raw_text = data.get("text")
                        if not isinstance(raw_text, str) or not raw_text.strip():
                            return False, None, None

                        safe_transcript_id: Optional[int] = None
                        raw_transcript_id = data.get("transcript_id")
                        if isinstance(raw_transcript_id, int):
                            transcript_exists = await session.execute(
                                sa.select(Transcript.id).where(
                                    Transcript.id == raw_transcript_id,
                                    Transcript.game_id == game_id,
                                )
                            )
                            if transcript_exists.scalar_one_or_none() is not None:
                                safe_transcript_id = raw_transcript_id

                        quote = ImportantQuote(
                            game_id=game_id,
                            note_id=audit_note_id,
                            transcript_id=safe_transcript_id,
                            text=raw_text,
                            speaker=(
                                data.get("speaker")
                                if isinstance(data.get("speaker"), str) or data.get("speaker") is None
                                else None
                            ),
                        )
                        session.add(quote)
                        await session.flush()
                        quote_id = quote.id
                        if quote_id is None:
                            return False, None, None
                        after = await _load_snapshot("important_quotes", quote_id)
                        return after is not None, quote_id, after

                    if table_name == "combat_updates":
                        raw_encounter = data.get("encounter")
                        raw_outcome = data.get("outcome")
                        if not isinstance(raw_encounter, str) or not isinstance(raw_outcome, str):
                            return False, None, None
                        combat = CombatUpdate(
                            game_id=game_id,
                            note_id=audit_note_id,
                            encounter=raw_encounter,
                            outcome=raw_outcome,
                        )
                        session.add(combat)
                        await session.flush()
                        combat_id = combat.id
                        if combat_id is None:
                            return False, None, None
                        _track_embedding_id("combat_updates", combat_id)
                        after = await _load_snapshot("combat_updates", combat_id)
                        return after is not None, combat_id, after

                    if table_name == "events":
                        raw_text = data.get("text")
                        if not isinstance(raw_text, str) or not raw_text.strip():
                            return False, None, None
                        text = raw_text.strip()
                        event_insert_stmt = (
                            pg_insert(Event)
                            .values(game_id=game_id, text=text)
                            .on_conflict_do_nothing(constraint="uq_events_game_text")
                            .returning(Event.id)
                        )
                        event_id = (await session.execute(event_insert_stmt)).scalar_one_or_none()
                        if event_id is None:
                            existing = await session.execute(
                                sa.select(Event.id).where(Event.game_id == game_id, Event.text == text)
                            )
                            event_id = existing.scalar_one_or_none()
                        if event_id is None:
                            return False, None, None
                        await session.execute(
                            pg_insert(notes_events_table)
                            .values(note_id=audit_note_id, event_id=event_id)
                            .on_conflict_do_nothing()
                        )
                        _track_embedding_id("events", event_id)
                        after = await _load_snapshot("events", event_id)
                        return after is not None, event_id, after

                    return False, None, None

                async def _apply_update(
                    table_name: str,
                    record_id: int,
                    changes: dict[str, Any],
                    before_snapshot: dict[str, Any],
                ) -> bool:
                    if table_name == "entities":
                        entity_values: dict[str, Any] = {}
                        if isinstance(changes.get("name"), str) and changes["name"].strip():
                            entity_values["name"] = changes["name"].strip()
                        if isinstance(changes.get("entity_type"), str) and changes["entity_type"].strip():
                            candidate_type = changes["entity_type"].strip().lower()
                            if candidate_type not in allowed_entity_types:
                                return False
                            entity_values["entity_type"] = candidate_type
                        if isinstance(changes.get("description"), str):
                            entity_values["description"] = changes["description"]
                        if not entity_values:
                            return False

                        next_name = entity_values.get("name", before_snapshot.get("name"))
                        next_type = entity_values.get("entity_type", before_snapshot.get("entity_type"))
                        collision = await session.execute(
                            sa.select(Entity.id)
                            .where(
                                Entity.game_id == game_id,
                                Entity.id != record_id,
                                Entity.name == next_name,
                                Entity.entity_type == next_type,
                            )
                            .limit(1)
                        )
                        if collision.scalar_one_or_none() is not None:
                            logger.warning(
                                "Skipping entity update due to uniqueness collision: game_id=%d entity_id=%d",
                                game_id,
                                record_id,
                            )
                            return False

                        entity_values["updated_at"] = sa.func.now()
                        result = await session.execute(
                            sa.update(Entity)
                            .where(Entity.id == record_id, Entity.game_id == game_id)
                            .values(**entity_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("entities", record_id)
                            return True
                        return False

                    if table_name == "quests":
                        quest_values: dict[str, Any] = {
                            "note_ids": sa.func.array_append(Quest.note_ids, audit_note_id),
                            "updated_at": sa.func.now(),
                        }
                        if isinstance(changes.get("name"), str) and changes["name"].strip():
                            next_name = changes["name"].strip()
                            collision = await session.execute(
                                sa.select(Quest.id)
                                .where(
                                    Quest.game_id == game_id,
                                    Quest.id != record_id,
                                    Quest.name == next_name,
                                )
                                .limit(1)
                            )
                            if collision.scalar_one_or_none() is not None:
                                logger.warning(
                                    "Skipping quest update due to uniqueness collision: game_id=%d quest_id=%d",
                                    game_id,
                                    record_id,
                                )
                                return False
                            quest_values["name"] = next_name

                        if isinstance(changes.get("description"), str):
                            new_description = changes["description"]
                            old_description = before_snapshot.get("description")
                            if isinstance(old_description, str) and old_description != new_description:
                                session.add(
                                    QuestDescriptionHistory(
                                        quest_id=record_id,
                                        description=old_description,
                                        note_id=audit_note_id,
                                    )
                                )
                            quest_values["description"] = new_description

                        if isinstance(changes.get("status"), str):
                            next_status = changes["status"].strip().lower()
                            if next_status in {"active", "completed"}:
                                quest_values["status"] = next_status

                        if "quest_giver_entity_id" in changes:
                            raw_entity_id = changes.get("quest_giver_entity_id")
                            if raw_entity_id is None:
                                quest_values["quest_giver_entity_id"] = None
                            elif isinstance(raw_entity_id, int):
                                entity_exists = await session.execute(
                                    sa.select(Entity.id).where(
                                        Entity.id == raw_entity_id,
                                        Entity.game_id == game_id,
                                    )
                                )
                                if entity_exists.scalar_one_or_none() is not None:
                                    quest_values["quest_giver_entity_id"] = raw_entity_id

                        result = await session.execute(
                            sa.update(Quest)
                            .where(
                                Quest.id == record_id,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                            .values(**quest_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("quests", record_id)
                            return True
                        return False

                    if table_name == "threads":
                        if changes.get("is_resolved") is False:
                            logger.warning(
                                "Skipping thread update that attempts reopening (is_resolved=false): "
                                "game_id=%d thread_id=%d",
                                game_id,
                                record_id,
                            )
                            return False

                        thread_values: dict[str, Any] = {}
                        if isinstance(changes.get("text"), str):
                            thread_values["text"] = changes["text"]
                        if isinstance(changes.get("resolution"), str):
                            thread_values["resolution"] = changes["resolution"]
                        if "quest_id" in changes:
                            raw_quest_id = changes.get("quest_id")
                            if raw_quest_id is None:
                                thread_values["quest_id"] = None
                            elif isinstance(raw_quest_id, int):
                                safe_quest_id = await _resolve_quest_reference(
                                    raw_quest_id=raw_quest_id,
                                    raw_quest_name=None,
                                )
                                if safe_quest_id is not None:
                                    thread_values["quest_id"] = safe_quest_id
                        if changes.get("is_resolved") is True:
                            thread_values["is_resolved"] = True
                            thread_values["resolved_by_note_id"] = audit_note_id
                            thread_values["resolved_at"] = sa.func.now()
                        if not thread_values:
                            return False

                        result = await session.execute(
                            sa.update(Thread)
                            .where(
                                Thread.id == record_id,
                                Thread.game_id == game_id,
                                Thread.is_deleted == False,  # noqa: E712
                            )
                            .values(**thread_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("threads", record_id)
                            return True
                        return False

                    if table_name == "events":
                        if not isinstance(changes.get("text"), str):
                            return False
                        next_text = changes["text"]
                        collision = await session.execute(
                            sa.select(Event.id)
                            .where(
                                Event.game_id == game_id,
                                Event.id != record_id,
                                Event.text == next_text,
                            )
                            .limit(1)
                        )
                        if collision.scalar_one_or_none() is not None:
                            logger.warning(
                                "Skipping event update due to uniqueness collision: game_id=%d event_id=%d",
                                game_id,
                                record_id,
                            )
                            return False
                        result = await session.execute(
                            sa.update(Event)
                            .where(Event.id == record_id, Event.game_id == game_id)
                            .values(text=next_text)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("events", record_id)
                            return True
                        return False

                    if table_name == "decisions":
                        decision_values: dict[str, Any] = {}
                        if isinstance(changes.get("decision"), str):
                            decision_values["decision"] = changes["decision"]
                        if isinstance(changes.get("made_by"), str):
                            decision_values["made_by"] = changes["made_by"]
                        if not decision_values:
                            return False
                        result = await session.execute(
                            sa.update(Decision)
                            .where(Decision.id == record_id, Decision.game_id == game_id)
                            .values(**decision_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("decisions", record_id)
                            return True
                        return False

                    if table_name == "loot":
                        loot_values: dict[str, Any] = {}
                        if isinstance(changes.get("item_name"), str) and changes["item_name"].strip():
                            loot_values["item_name"] = changes["item_name"].strip()
                        if isinstance(changes.get("acquired_by"), str) and changes["acquired_by"].strip():
                            loot_values["acquired_by"] = changes["acquired_by"].strip()
                        if "quest_id" in changes:
                            raw_quest_id = changes.get("quest_id")
                            if raw_quest_id is None:
                                loot_values["quest_id"] = None
                            elif isinstance(raw_quest_id, int):
                                safe_quest_id = await _resolve_quest_reference(
                                    raw_quest_id=raw_quest_id,
                                    raw_quest_name=None,
                                )
                                if safe_quest_id is not None:
                                    loot_values["quest_id"] = safe_quest_id
                        if not loot_values:
                            return False

                        next_item_name = loot_values.get("item_name", before_snapshot.get("item_name"))
                        next_acquired_by = loot_values.get("acquired_by", before_snapshot.get("acquired_by"))
                        collision = await session.execute(
                            sa.select(Loot.id)
                            .where(
                                Loot.game_id == game_id,
                                Loot.id != record_id,
                                Loot.item_name == next_item_name,
                                Loot.acquired_by == next_acquired_by,
                            )
                            .limit(1)
                        )
                        if collision.scalar_one_or_none() is not None:
                            logger.warning(
                                "Skipping loot update due to uniqueness collision: game_id=%d loot_id=%d",
                                game_id,
                                record_id,
                            )
                            return False

                        result = await session.execute(
                            sa.update(Loot)
                            .where(Loot.id == record_id, Loot.game_id == game_id)
                            .values(**loot_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("loot", record_id)
                            return True
                        return False

                    if table_name == "important_quotes":
                        quote_values: dict[str, Any] = {}
                        if isinstance(changes.get("text"), str):
                            quote_values["text"] = changes["text"]
                        if "speaker" in changes and (
                            changes.get("speaker") is None or isinstance(changes.get("speaker"), str)
                        ):
                            quote_values["speaker"] = changes.get("speaker")
                        if "transcript_id" in changes:
                            raw_tid = changes.get("transcript_id")
                            if raw_tid is None:
                                quote_values["transcript_id"] = None
                            elif isinstance(raw_tid, int):
                                transcript_exists = await session.execute(
                                    sa.select(Transcript.id).where(
                                        Transcript.id == raw_tid,
                                        Transcript.game_id == game_id,
                                    )
                                )
                                if transcript_exists.scalar_one_or_none() is not None:
                                    quote_values["transcript_id"] = raw_tid
                        if not quote_values:
                            return False
                        result = await session.execute(
                            sa.update(ImportantQuote)
                            .where(ImportantQuote.id == record_id, ImportantQuote.game_id == game_id)
                            .values(**quote_values)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "combat_updates":
                        combat_values: dict[str, Any] = {}
                        if isinstance(changes.get("encounter"), str):
                            combat_values["encounter"] = changes["encounter"]
                        if isinstance(changes.get("outcome"), str):
                            combat_values["outcome"] = changes["outcome"]
                        if not combat_values:
                            return False
                        result = await session.execute(
                            sa.update(CombatUpdate)
                            .where(CombatUpdate.id == record_id, CombatUpdate.game_id == game_id)
                            .values(**combat_values)
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("combat_updates", record_id)
                            return True
                        return False

                    return False

                async def _apply_delete(table_name: str, record_id: int, reason: str) -> bool:
                    if table_name == "quests":
                        existing = await session.execute(
                            sa.select(Quest.is_deleted).where(Quest.id == record_id, Quest.game_id == game_id)
                        )
                        quest_deleted = existing.scalar_one_or_none()
                        if quest_deleted is None:
                            return False
                        if quest_deleted:
                            return True
                        result = await session.execute(
                            sa.update(Quest)
                            .where(
                                Quest.id == record_id,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                            .values(
                                is_deleted=True,
                                deleted_at=sa.func.now(),
                                deleted_reason=reason,
                                updated_at=sa.func.now(),
                            )
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("quests", record_id)
                            return True
                        return False

                    if table_name == "threads":
                        existing = await session.execute(
                            sa.select(Thread.is_deleted).where(Thread.id == record_id, Thread.game_id == game_id)
                        )
                        thread_deleted = existing.scalar_one_or_none()
                        if thread_deleted is None:
                            return False
                        if thread_deleted:
                            return True
                        result = await session.execute(
                            sa.update(Thread)
                            .where(
                                Thread.id == record_id,
                                Thread.game_id == game_id,
                                Thread.is_deleted == False,  # noqa: E712
                            )
                            .values(
                                is_deleted=True,
                                deleted_at=sa.func.now(),
                                deleted_reason=reason,
                            )
                        )
                        if _affected_rows(result) > 0:
                            _track_embedding_id("threads", record_id)
                            return True
                        return False

                    if table_name == "entities":
                        entity = await session.get(Entity, record_id)
                        if entity is None or entity.game_id != game_id:
                            return False
                        await session.execute(
                            sa.update(Quest)
                            .where(Quest.game_id == game_id, Quest.quest_giver_entity_id == record_id)
                            .values(quest_giver_entity_id=None, updated_at=sa.func.now())
                        )
                        await session.execute(
                            sa.delete(notes_entities_table).where(notes_entities_table.c.entity_id == record_id)
                        )
                        result = await session.execute(
                            sa.delete(Entity).where(Entity.id == record_id, Entity.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "events":
                        await session.execute(
                            sa.delete(notes_events_table).where(notes_events_table.c.event_id == record_id)
                        )
                        result = await session.execute(
                            sa.delete(Event).where(Event.id == record_id, Event.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "loot":
                        await session.execute(
                            sa.delete(notes_loot_table).where(notes_loot_table.c.loot_id == record_id)
                        )
                        result = await session.execute(
                            sa.delete(Loot).where(Loot.id == record_id, Loot.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "decisions":
                        result = await session.execute(
                            sa.delete(Decision).where(Decision.id == record_id, Decision.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "important_quotes":
                        result = await session.execute(
                            sa.delete(ImportantQuote)
                            .where(ImportantQuote.id == record_id, ImportantQuote.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    if table_name == "combat_updates":
                        result = await session.execute(
                            sa.delete(CombatUpdate)
                            .where(CombatUpdate.id == record_id, CombatUpdate.game_id == game_id)
                        )
                        return _affected_rows(result) > 0

                    return False

                async def _apply_merge(table_name: str, canonical_id: int, duplicate_id: int) -> bool:
                    if canonical_id == duplicate_id:
                        return True

                    if table_name == "entities":
                        canonical_game_id = (await session.execute(
                            sa.select(Entity.game_id).where(Entity.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(Entity.game_id).where(Entity.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False

                        duplicate_note_rows = await session.execute(
                            sa.select(notes_entities_table.c.note_id)
                            .where(notes_entities_table.c.entity_id == duplicate_id)
                        )
                        for note_id in [row[0] for row in duplicate_note_rows.all()]:
                            await session.execute(
                                pg_insert(notes_entities_table)
                                .values(note_id=note_id, entity_id=canonical_id)
                                .on_conflict_do_nothing()
                            )

                        await session.execute(
                            sa.update(Quest)
                            .where(Quest.game_id == game_id, Quest.quest_giver_entity_id == duplicate_id)
                            .values(quest_giver_entity_id=canonical_id, updated_at=sa.func.now())
                        )
                        await session.execute(
                            sa.delete(notes_entities_table).where(notes_entities_table.c.entity_id == duplicate_id)
                        )
                        deleted = await session.execute(
                            sa.delete(Entity).where(Entity.id == duplicate_id, Entity.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("entities", canonical_id)
                            return True
                        return False

                    if table_name == "events":
                        canonical_game_id = (await session.execute(
                            sa.select(Event.game_id).where(Event.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(Event.game_id).where(Event.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False

                        duplicate_note_rows = await session.execute(
                            sa.select(notes_events_table.c.note_id)
                            .where(notes_events_table.c.event_id == duplicate_id)
                        )
                        for note_id in [row[0] for row in duplicate_note_rows.all()]:
                            await session.execute(
                                pg_insert(notes_events_table)
                                .values(note_id=note_id, event_id=canonical_id)
                                .on_conflict_do_nothing()
                            )

                        await session.execute(
                            sa.delete(notes_events_table).where(notes_events_table.c.event_id == duplicate_id)
                        )
                        deleted = await session.execute(
                            sa.delete(Event).where(Event.id == duplicate_id, Event.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("events", canonical_id)
                            return True
                        return False

                    if table_name == "loot":
                        canonical_game_id = (await session.execute(
                            sa.select(Loot.game_id).where(Loot.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(Loot.game_id).where(Loot.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False

                        duplicate_note_rows = await session.execute(
                            sa.select(notes_loot_table.c.note_id)
                            .where(notes_loot_table.c.loot_id == duplicate_id)
                        )
                        for note_id in [row[0] for row in duplicate_note_rows.all()]:
                            await session.execute(
                                pg_insert(notes_loot_table)
                                .values(note_id=note_id, loot_id=canonical_id)
                                .on_conflict_do_nothing()
                            )

                        await session.execute(
                            sa.delete(notes_loot_table).where(notes_loot_table.c.loot_id == duplicate_id)
                        )
                        deleted = await session.execute(
                            sa.delete(Loot).where(Loot.id == duplicate_id, Loot.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("loot", canonical_id)
                            return True
                        return False

                    if table_name == "quests":
                        canonical_row = (await session.execute(
                            sa.select(Quest.game_id, Quest.note_ids).where(Quest.id == canonical_id)
                        )).one_or_none()
                        duplicate_row = (await session.execute(
                            sa.select(Quest.game_id, Quest.note_ids).where(Quest.id == duplicate_id)
                        )).one_or_none()
                        if canonical_row is None or duplicate_row is None:
                            return False
                        canonical_game_id, canonical_note_ids = canonical_row
                        duplicate_game_id, duplicate_note_ids = duplicate_row
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False

                        merged_note_ids: list[int] = []
                        seen_note_ids: set[int] = set()
                        for candidate_id in [*(canonical_note_ids or []), *(duplicate_note_ids or [])]:
                            if isinstance(candidate_id, int) and candidate_id not in seen_note_ids:
                                seen_note_ids.add(candidate_id)
                                merged_note_ids.append(candidate_id)

                        await session.execute(
                            sa.update(Quest)
                            .where(Quest.id == canonical_id, Quest.game_id == game_id)
                            .values(note_ids=merged_note_ids, updated_at=sa.func.now())
                        )
                        await session.execute(
                            sa.update(Thread)
                            .where(Thread.game_id == game_id, Thread.quest_id == duplicate_id)
                            .values(quest_id=canonical_id)
                        )
                        await session.execute(
                            sa.update(Loot)
                            .where(Loot.game_id == game_id, Loot.quest_id == duplicate_id)
                            .values(quest_id=canonical_id)
                        )
                        deleted = await session.execute(
                            sa.delete(Quest).where(Quest.id == duplicate_id, Quest.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("quests", canonical_id)
                            return True
                        return False

                    if table_name == "threads":
                        canonical_game_id = (await session.execute(
                            sa.select(Thread.game_id).where(Thread.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(Thread.game_id).where(Thread.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False
                        deleted = await session.execute(
                            sa.delete(Thread).where(Thread.id == duplicate_id, Thread.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("threads", canonical_id)
                            return True
                        return False

                    if table_name == "decisions":
                        canonical_game_id = (await session.execute(
                            sa.select(Decision.game_id).where(Decision.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(Decision.game_id).where(Decision.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False
                        deleted = await session.execute(
                            sa.delete(Decision).where(Decision.id == duplicate_id, Decision.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("decisions", canonical_id)
                            return True
                        return False

                    if table_name == "important_quotes":
                        canonical_game_id = (await session.execute(
                            sa.select(ImportantQuote.game_id).where(ImportantQuote.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(ImportantQuote.game_id).where(ImportantQuote.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False
                        deleted = await session.execute(
                            sa.delete(ImportantQuote)
                            .where(ImportantQuote.id == duplicate_id, ImportantQuote.game_id == game_id)
                        )
                        return _affected_rows(deleted) > 0

                    if table_name == "combat_updates":
                        canonical_game_id = (await session.execute(
                            sa.select(CombatUpdate.game_id).where(CombatUpdate.id == canonical_id)
                        )).scalar_one_or_none()
                        duplicate_game_id = (await session.execute(
                            sa.select(CombatUpdate.game_id).where(CombatUpdate.id == duplicate_id)
                        )).scalar_one_or_none()
                        if canonical_game_id != game_id or duplicate_game_id != game_id:
                            return False
                        deleted = await session.execute(
                            sa.delete(CombatUpdate)
                            .where(CombatUpdate.id == duplicate_id, CombatUpdate.game_id == game_id)
                        )
                        if _affected_rows(deleted) > 0:
                            _track_embedding_id("combat_updates", canonical_id)
                            return True
                        return False

                    return False

                run_result = await session.execute(
                    sa.select(AuditRun)
                    .where(AuditRun.id == audit_run_id)
                    .with_for_update()
                )
                run = run_result.scalar_one_or_none()
                if run is None:
                    raise ValueError(f"audit_run_id={audit_run_id} does not exist")
                if run.game_id != game_id:
                    raise ValueError(
                        f"audit_run_id={audit_run_id} belongs to game_id={run.game_id}, not {game_id}"
                    )
                if run.status != "running":
                    raise ValueError(f"audit_run_id={audit_run_id} is not running (status={run.status})")

                # Phase A: creates (three ordered passes with flushes and name maps)
                for create_op in table_changesets["entities"]["creates"]:
                    confidence = _normalize_confidence(create_op, context="entities.create")
                    description = _normalize_description(
                        create_op,
                        fallback="Create entity from audit output",
                    )
                    data = _coerce_dict(create_op.get("data"), fallback_label="entity create data")
                    status = "pending"
                    after_snapshot = None

                    if confidence == "high":
                        applied, created_id, after_snapshot = await _apply_create("entities", data)
                        if applied and created_id is not None:
                            status = "applied"
                            normalized_name = _normalize_name(data.get("name"))
                            if normalized_name is not None:
                                entity_name_to_id[normalized_name] = created_id

                    _append_flag(
                        operation="create",
                        table_name="entities",
                        confidence=confidence,
                        target_id=None,
                        description=description,
                        suggested_change={
                            "data": data,
                            "_before": None,
                            "_after": after_snapshot if status == "applied" else None,
                        },
                        status=status,
                    )

                await session.flush()

                for create_op in table_changesets["quests"]["creates"]:
                    confidence = _normalize_confidence(create_op, context="quests.create")
                    description = _normalize_description(
                        create_op,
                        fallback="Create quest from audit output",
                    )
                    data = _coerce_dict(create_op.get("data"), fallback_label="quest create data")
                    status = "pending"
                    after_snapshot = None

                    if confidence == "high":
                        applied, created_id, after_snapshot = await _apply_create("quests", data)
                        if applied and created_id is not None:
                            status = "applied"
                            normalized_name = _normalize_name(data.get("name"))
                            if normalized_name is not None:
                                quest_name_to_id[normalized_name] = created_id

                    _append_flag(
                        operation="create",
                        table_name="quests",
                        confidence=confidence,
                        target_id=None,
                        description=description,
                        suggested_change={
                            "data": data,
                            "_before": None,
                            "_after": after_snapshot if status == "applied" else None,
                        },
                        status=status,
                    )

                await session.flush()

                pass_three_tables = (
                    "threads",
                    "loot",
                    "decisions",
                    "important_quotes",
                    "combat_updates",
                    "events",
                )
                for table_name in pass_three_tables:
                    for create_op in table_changesets[table_name]["creates"]:
                        confidence = _normalize_confidence(create_op, context=f"{table_name}.create")
                        description = _normalize_description(
                            create_op,
                            fallback=f"Create {table_name} row from audit output",
                        )
                        data = _coerce_dict(
                            create_op.get("data"),
                            fallback_label=f"{table_name} create data",
                        )
                        status = "pending"
                        after_snapshot = None

                        if confidence == "high":
                            applied, _created_id, after_snapshot = await _apply_create(table_name, data)
                            if applied:
                                status = "applied"

                        _append_flag(
                            operation="create",
                            table_name=table_name,
                            confidence=confidence,
                            target_id=None,
                            description=description,
                            suggested_change={
                                "data": data,
                                "_before": None,
                                "_after": after_snapshot if status == "applied" else None,
                            },
                            status=status,
                        )

                await session.flush()

                # Phase B: updates / deletes / merges across all tables.
                for table_name in table_order:
                    for update_op in table_changesets[table_name]["updates"]:
                        confidence = _normalize_confidence(update_op, context=f"{table_name}.update")
                        description = _normalize_description(
                            update_op,
                            fallback=f"Update {table_name} row from audit output",
                        )
                        target_id = update_op.get("id") if isinstance(update_op.get("id"), int) else None
                        changes = _coerce_dict(
                            update_op.get("changes"),
                            fallback_label=f"{table_name} update changes",
                        )

                        before_snapshot = None
                        if target_id is not None:
                            before_snapshot = await _load_snapshot(table_name, target_id)
                        if before_snapshot is None:
                            logger.warning(
                                "Missing _before snapshot for %s update id=%s (game_id=%d)",
                                table_name,
                                target_id,
                                game_id,
                            )

                        status = "pending"
                        after_snapshot = None
                        if confidence == "high" and target_id is not None and before_snapshot is not None:
                            applied = await _apply_update(table_name, target_id, changes, before_snapshot)
                            if applied:
                                after_snapshot = await _load_snapshot(table_name, target_id)
                                if after_snapshot is not None:
                                    status = "applied"

                        _append_flag(
                            operation="update",
                            table_name=table_name,
                            confidence=confidence,
                            target_id=target_id,
                            description=description,
                            suggested_change={
                                "changes": changes,
                                "_before": before_snapshot,
                                "_after": after_snapshot if status == "applied" else None,
                            },
                            status=status,
                        )

                    for delete_op in table_changesets[table_name]["deletes"]:
                        confidence = _normalize_confidence(delete_op, context=f"{table_name}.delete")
                        description = _normalize_description(
                            delete_op,
                            fallback=f"Delete {table_name} row from audit output",
                        )
                        target_id = delete_op.get("id") if isinstance(delete_op.get("id"), int) else None

                        before_snapshot = None
                        if target_id is not None:
                            before_snapshot = await _load_snapshot(table_name, target_id)
                        if before_snapshot is None:
                            logger.warning(
                                "Missing _before snapshot for %s delete id=%s (game_id=%d)",
                                table_name,
                                target_id,
                                game_id,
                            )

                        status = "pending"
                        if confidence == "high" and target_id is not None and before_snapshot is not None:
                            applied = await _apply_delete(table_name, target_id, description)
                            if applied:
                                status = "applied"

                        _append_flag(
                            operation="delete",
                            table_name=table_name,
                            confidence=confidence,
                            target_id=target_id,
                            description=description,
                            suggested_change={
                                "_before": before_snapshot,
                                "_after": None,
                            },
                            status=status,
                        )

                    for merge_op in table_changesets[table_name]["merges"]:
                        confidence = _normalize_confidence(merge_op, context=f"{table_name}.merge")
                        description = _normalize_description(
                            merge_op,
                            fallback=f"Merge duplicate {table_name} rows from audit output",
                        )
                        canonical_id = (
                            merge_op.get("canonical_id")
                            if isinstance(merge_op.get("canonical_id"), int)
                            else None
                        )
                        duplicate_id = (
                            merge_op.get("duplicate_id")
                            if isinstance(merge_op.get("duplicate_id"), int)
                            else None
                        )

                        canonical_snapshot: Optional[dict[str, Any]] = None
                        duplicate_snapshot: Optional[dict[str, Any]] = None
                        if canonical_id is not None:
                            canonical_snapshot = await _load_snapshot(table_name, canonical_id)
                        if duplicate_id is not None:
                            duplicate_snapshot = await _load_snapshot(table_name, duplicate_id)
                        if canonical_snapshot is None or duplicate_snapshot is None:
                            logger.warning(
                                "Missing merge snapshot for %s canonical=%s duplicate=%s (game_id=%d)",
                                table_name,
                                canonical_id,
                                duplicate_id,
                                game_id,
                            )

                        status = "pending"
                        if (
                            confidence == "high"
                            and canonical_id is not None
                            and duplicate_id is not None
                            and canonical_snapshot is not None
                            and duplicate_snapshot is not None
                        ):
                            applied = await _apply_merge(table_name, canonical_id, duplicate_id)
                            if applied:
                                status = "applied"

                        _append_flag(
                            operation="merge",
                            table_name=table_name,
                            confidence=confidence,
                            target_id=None,
                            description=description,
                            suggested_change={
                                "canonical_id": canonical_id,
                                "duplicate_id": duplicate_id,
                                "_canonical": canonical_snapshot,
                                "_duplicate": duplicate_snapshot,
                            },
                            status=status,
                        )

                await session.execute(
                    sa.update(AuditRun)
                    .where(AuditRun.id == audit_run_id)
                    .values(
                        status="completed",
                        completed_at=sa.func.now(),
                        heartbeat_at=sa.func.now(),
                        notes_audited=note_ids_audited,
                        notes_audited_count=len(note_ids_audited),
                        min_note_id=min_note_id,
                        max_note_id=max_note_id,
                        audit_note_id=audit_note_id,
                    )
                )

        return AuditPipelineResult(
            audit_run_id=audit_run_id,
            audit_note_id=audit_note_id,
            entity_ids=sorted(entity_ids_to_embed),
            thread_ids=sorted(thread_ids_to_embed),
            event_ids=sorted(event_ids_to_embed),
            decision_ids=sorted(decision_ids_to_embed),
            loot_ids=sorted(loot_ids_to_embed),
            quest_ids=sorted(quest_ids_to_embed),
            combat_ids=sorted(combat_ids_to_embed),
        )
    except Exception:
        logger.exception(
            "write_audit_pipeline_result failed; failing audit run and cleaning synthetic note "
            "(game_id=%d audit_run_id=%d)",
            game_id,
            audit_run_id,
        )
        try:
            did_fail = await fail_audit_run(audit_run_id)
            if not did_fail:
                logger.error(
                    "Failed to mark audit run as failed (no row updated); stale-running risk may remain: "
                    "audit_run_id=%d",
                    audit_run_id,
                )
        except Exception:
            logger.exception("Failed to mark audit run as failed: audit_run_id=%d", audit_run_id)
        try:
            async with AsyncSessionLocal() as cleanup_session:
                async with cleanup_session.begin():
                    await cleanup_session.execute(
                        sa.delete(Note).where(
                            Note.id == audit_note_id,
                            Note.game_id == game_id,
                            Note.is_audit == True,  # noqa: E712
                        )
                    )
        except Exception:
            logger.exception(
                "Best-effort synthetic audit note cleanup failed: note_id=%s run_id=%d",
                audit_note_id,
                audit_run_id,
            )
        raise


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
                    Thread.is_deleted == False,  # noqa: E712
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
                    Thread.is_deleted == False,  # noqa: E712
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
                    Thread.is_deleted == False,  # noqa: E712
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
                    Thread.is_deleted == False,  # noqa: E712
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
                .where(
                    Quest.game_id == game_id,
                    Quest.is_deleted == False,  # noqa: E712
                    Quest.embedding.is_not(None),
                )
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
                    Quest.is_deleted == False,  # noqa: E712
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


async def _write_flag_embeddings(embed_ids: dict[str, list[int]]) -> None:
    """Post-commit embedding write pass for rows touched by manual flag apply."""
    delays = [5, 15, 45]
    table_specs = [
        ("entities", Entity, lambda e: f"[{e.entity_type}] {e.name}: {e.description}"),
        (
            "threads",
            Thread,
            lambda t: f"{t.text} — Resolution: {t.resolution or ''}" if t.is_resolved else t.text,
        ),
        ("events", Event, lambda e: e.text),
        ("decisions", Decision, lambda d: f"Decision by {d.made_by}: {d.decision}"),
        ("loot", Loot, lambda loot: f"Loot acquired by {loot.acquired_by}: {loot.item_name}"),
        ("quests", Quest, lambda q: f"[Quest] {q.name}: {q.description}"),
        (
            "combat_updates",
            CombatUpdate,
            lambda c: f"Combat encounter: {c.encounter} — Outcome: {c.outcome}",
        ),
    ]

    for attempt, delay in enumerate(delays, start=1):
        try:
            to_embed: list[tuple[type, int, str]] = []
            async with AsyncSessionLocal() as session:
                for table_name, model_cls, text_fn in table_specs:
                    for row_id in sorted(set(embed_ids.get(table_name) or [])):
                        row = await session.get(model_cls, row_id)
                        if row is not None:
                            to_embed.append((model_cls, row_id, text_fn(row)))

            if not to_embed:
                return

            model_classes, pks, texts = zip(*to_embed)
            vecs = await _embed_texts(list(texts))

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    for model_cls, pk, vec in zip(model_classes, pks, vecs):
                        obj = await session.get(model_cls, pk)
                        if obj is not None:
                            obj.embedding = vec  # type: ignore[attr-defined]
            return
        except Exception:
            if attempt == len(delays):
                logger.exception(
                    "Failed to write flag embeddings after %d attempts (embed_ids=%s)",
                    attempt,
                    embed_ids,
                )
                return
            logger.warning(
                "Flag embedding write attempt %d/%d failed; retrying in %ss (embed_ids=%s)",
                attempt,
                len(delays),
                delay,
                embed_ids,
                exc_info=True,
            )
            await asyncio.sleep(delay)


async def _write_audit_embeddings(result: AuditPipelineResult) -> None:
    """Post-commit embedding pass for audit pipeline outputs.

    Retries with bounded exponential backoff (5s, 15s, 45s).
    """
    delays = [5, 15, 45]
    for attempt, delay in enumerate(delays, start=1):
        try:
            to_embed: list[tuple[type, int, str]] = []
            async with AsyncSessionLocal() as session:
                for eid in result.entity_ids:
                    entity = await session.get(Entity, eid)
                    if entity:
                        to_embed.append((Entity, eid, f"[{entity.entity_type}] {entity.name}: {entity.description}"))

                for tid in result.thread_ids:
                    thread = await session.get(Thread, tid)
                    if thread:
                        text = f"{thread.text} — Resolution: {thread.resolution or ''}" if thread.is_resolved else thread.text
                        to_embed.append((Thread, tid, text))

                for eid in result.event_ids:
                    event = await session.get(Event, eid)
                    if event:
                        to_embed.append((Event, eid, event.text))

                note = await session.get(Note, result.audit_note_id)
                if note:
                    to_embed.append((Note, result.audit_note_id, note.summary))

                for did in result.decision_ids:
                    decision = await session.get(Decision, did)
                    if decision:
                        to_embed.append((Decision, did, f"Decision by {decision.made_by}: {decision.decision}"))

                for lid in result.loot_ids:
                    loot_row = await session.get(Loot, lid)
                    if loot_row:
                        to_embed.append((Loot, lid, f"Loot acquired by {loot_row.acquired_by}: {loot_row.item_name}"))

                for qid in result.quest_ids:
                    quest = await session.get(Quest, qid)
                    if quest:
                        to_embed.append((Quest, qid, f"[Quest] {quest.name}: {quest.description}"))

                for cid in result.combat_ids:
                    combat = await session.get(CombatUpdate, cid)
                    if combat:
                        to_embed.append((CombatUpdate, cid, f"Combat encounter: {combat.encounter} — Outcome: {combat.outcome}"))

                # ImportantQuote is intentionally excluded: it has no embedding column.

            if not to_embed:
                return

            model_classes, pks, texts = zip(*to_embed)
            vecs = await _embed_texts(list(texts))

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    for model_cls, pk, vec in zip(model_classes, pks, vecs):
                        obj = await session.get(model_cls, pk)
                        if obj is not None:
                            obj.embedding = vec  # type: ignore[attr-defined]
            return
        except Exception:
            if attempt == len(delays):
                logger.exception(
                    "Failed to write audit embeddings after %d attempts (audit_run_id=%d audit_note_id=%d)",
                    attempt,
                    result.audit_run_id,
                    result.audit_note_id,
                )
                return
            logger.warning(
                "Audit embedding write attempt %d/%d failed; retrying in %ss "
                "(audit_run_id=%d audit_note_id=%d)",
                attempt,
                len(delays),
                delay,
                result.audit_run_id,
                result.audit_note_id,
                exc_info=True,
            )
            await asyncio.sleep(delay)


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
