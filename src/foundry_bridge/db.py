import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

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


async def _apply_flag_change(
    session,
    flag: AuditFlag,
) -> tuple[bool, bool, str, str, dict[str, Any]]:
    change = flag.suggested_change or {}

    if flag.flag_type == "entity_duplicate":
        canonical_id = change.get("canonical_id")
        duplicate_id = change.get("duplicate_id")
        if not isinstance(canonical_id, int) or not isinstance(duplicate_id, int):
            return False, False, "invalid_shape", "entity_duplicate requires canonical_id and duplicate_id", {}
        if canonical_id == duplicate_id:
            return True, True, "noop_same_entity", "entity_duplicate points to identical IDs", {
                "canonical_id": canonical_id,
                "duplicate_id": duplicate_id,
            }

        canonical = await session.get(Entity, canonical_id)
        duplicate = await session.get(Entity, duplicate_id)
        if canonical is None or duplicate is None:
            return False, False, "not_found", "Canonical or duplicate entity not found", {
                "canonical_id": canonical_id,
                "duplicate_id": duplicate_id,
            }
        if canonical.game_id != flag.game_id or duplicate.game_id != flag.game_id:
            return False, False, "cross_game", "Entities do not belong to audit flag game", {
                "canonical_game_id": canonical.game_id,
                "duplicate_game_id": duplicate.game_id,
                "flag_game_id": flag.game_id,
            }

        duplicate_note_rows = await session.execute(
            sa.select(notes_entities_table.c.note_id).where(
                notes_entities_table.c.entity_id == duplicate_id
            )
        )
        duplicate_note_ids = [row[0] for row in duplicate_note_rows.all()]
        for note_id in duplicate_note_ids:
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
        await session.execute(
            sa.delete(Entity).where(Entity.id == duplicate_id, Entity.game_id == flag.game_id)
        )
        return True, False, "applied", "Merged duplicate entity into canonical entity", {
            "canonical_id": canonical_id,
            "duplicate_id": duplicate_id,
        }

    if flag.flag_type == "missing_entity":
        name = change.get("name")
        entity_type = change.get("entity_type")
        description = change.get("description")
        if not isinstance(name, str) or not isinstance(entity_type, str) or not isinstance(description, str):
            return False, False, "invalid_shape", "missing_entity requires name/entity_type/description", {}

        entity_insert_stmt = pg_insert(Entity).values(
            game_id=flag.game_id,
            entity_type=entity_type,
            name=name,
            description=description,
        )
        entity_upsert_stmt = entity_insert_stmt.on_conflict_do_update(
            constraint="uq_entities_game_entity_type_name",
            set_={
                "description": entity_insert_stmt.excluded.description,
                "updated_at": sa.func.now(),
            },
        ).returning(Entity.id)
        entity_result = await session.execute(entity_upsert_stmt)
        entity_id = entity_result.scalar_one()

        audit_note_id_result = await session.execute(
            sa.select(AuditRun.audit_note_id).where(AuditRun.id == flag.audit_run_id)
        )
        audit_note_id = audit_note_id_result.scalar_one_or_none()
        if audit_note_id is not None:
            await session.execute(
                pg_insert(notes_entities_table)
                .values(note_id=audit_note_id, entity_id=entity_id)
                .on_conflict_do_nothing()
            )

        return True, False, "applied", "Missing entity inserted/upserted", {
            "entity_id": entity_id,
            "linked_audit_note_id": audit_note_id,
        }

    if flag.flag_type == "deletion_candidate":
        table_name = change.get("table")
        record_id = change.get("record_id")
        reason = change.get("reason") or "audit flag deletion candidate"
        if not isinstance(table_name, str) or not isinstance(record_id, int):
            return False, False, "invalid_shape", "deletion_candidate requires table and record_id", {}

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
        }
        table_name = table_aliases.get(table_name.strip().lower(), table_name)

        if table_name == "quests":
            quest = await session.get(Quest, record_id)
            if quest is None or quest.game_id != flag.game_id:
                return False, False, "not_found", "Quest deletion candidate not found", {"record_id": record_id}
            if quest.is_deleted:
                return True, True, "already_deleted", "Quest already soft-deleted", {"record_id": record_id}
            await session.execute(
                sa.update(Quest)
                .where(Quest.id == record_id, Quest.game_id == flag.game_id)
                .values(
                    is_deleted=True,
                    deleted_at=sa.func.now(),
                    deleted_reason=reason,
                    updated_at=sa.func.now(),
                )
            )
            return True, False, "applied", "Quest soft-deleted", {"record_id": record_id}

        if table_name == "threads":
            thread = await session.get(Thread, record_id)
            if thread is None or thread.game_id != flag.game_id:
                return False, False, "not_found", "Thread deletion candidate not found", {"record_id": record_id}
            if thread.is_deleted:
                return True, True, "already_deleted", "Thread already soft-deleted", {"record_id": record_id}
            await session.execute(
                sa.update(Thread)
                .where(Thread.id == record_id, Thread.game_id == flag.game_id)
                .values(
                    is_deleted=True,
                    deleted_at=sa.func.now(),
                    deleted_reason=reason,
                )
            )
            return True, False, "applied", "Thread soft-deleted", {"record_id": record_id}

        if table_name == "entities":
            entity = await session.get(Entity, record_id)
            if entity is None or entity.game_id != flag.game_id:
                return False, False, "not_found", "Entity deletion candidate not found", {"record_id": record_id}
            await session.execute(
                sa.update(Quest)
                .where(Quest.game_id == flag.game_id, Quest.quest_giver_entity_id == record_id)
                .values(quest_giver_entity_id=None, updated_at=sa.func.now())
            )
            await session.execute(
                sa.delete(notes_entities_table).where(notes_entities_table.c.entity_id == record_id)
            )
            await session.execute(
                sa.delete(Entity).where(Entity.id == record_id, Entity.game_id == flag.game_id)
            )
            return True, False, "applied", "Entity hard-deleted", {"record_id": record_id}

        if table_name == "events":
            await session.execute(sa.delete(notes_events_table).where(notes_events_table.c.event_id == record_id))
            result = await session.execute(
                sa.delete(Event).where(Event.id == record_id, Event.game_id == flag.game_id)
            )
            if _affected_rows(result) == 0:
                return False, False, "not_found", "Event deletion candidate not found", {"record_id": record_id}
            return True, False, "applied", "Event hard-deleted", {"record_id": record_id}

        if table_name == "loot":
            await session.execute(sa.delete(notes_loot_table).where(notes_loot_table.c.loot_id == record_id))
            result = await session.execute(
                sa.delete(Loot).where(Loot.id == record_id, Loot.game_id == flag.game_id)
            )
            if _affected_rows(result) == 0:
                return False, False, "not_found", "Loot deletion candidate not found", {"record_id": record_id}
            return True, False, "applied", "Loot hard-deleted", {"record_id": record_id}

        if table_name == "decisions":
            result = await session.execute(
                sa.delete(Decision).where(Decision.id == record_id, Decision.game_id == flag.game_id)
            )
            if _affected_rows(result) == 0:
                return False, False, "not_found", "Decision deletion candidate not found", {"record_id": record_id}
            return True, False, "applied", "Decision hard-deleted", {"record_id": record_id}

        if table_name == "important_quotes":
            result = await session.execute(
                sa.delete(ImportantQuote).where(
                    ImportantQuote.id == record_id,
                    ImportantQuote.game_id == flag.game_id,
                )
            )
            if _affected_rows(result) == 0:
                return (
                    False,
                    False,
                    "not_found",
                    "Important quote deletion candidate not found",
                    {"record_id": record_id},
                )
            return True, False, "applied", "Important quote hard-deleted", {"record_id": record_id}

        return False, False, "unsupported_table", "Unsupported deletion_candidate table", {
            "table": table_name
        }

    return False, False, "unsupported_flag_type", "Unsupported or invalid audit flag shape", {
        "flag_type": flag.flag_type
    }


async def apply_audit_flag(flag_id: int) -> AuditFlagMutationResult:
    """Apply an audit flag action with idempotent status semantics."""
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

            ok, noop, reason_code, message, details = await _apply_flag_change(session, flag)
            if not ok:
                return _flag_result(
                    flag_id=flag.id,
                    ok=False,
                    noop=noop,
                    status=flag.status,
                    reason_code=reason_code,
                    message=message,
                    details=details,
                )

            await session.execute(
                sa.update(AuditFlag)
                .where(AuditFlag.id == flag.id)
                .values(status="applied", resolved_at=sa.func.now())
            )
            return _flag_result(
                flag_id=flag.id,
                ok=True,
                noop=noop,
                status="applied",
                reason_code=reason_code,
                message=message,
                details=details,
            )


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

    entity_description_updates = _model_list_to_dicts(output_payload.get("entity_description_updates"))
    quest_description_updates = _model_list_to_dicts(output_payload.get("quest_description_updates"))
    quest_status_updates = _model_list_to_dicts(output_payload.get("quest_status_updates"))
    thread_resolutions = _model_list_to_dicts(output_payload.get("thread_resolutions"))
    thread_text_updates = _model_list_to_dicts(output_payload.get("thread_text_updates"))
    event_text_updates = _model_list_to_dicts(output_payload.get("event_text_updates"))
    decision_corrections = _model_list_to_dicts(output_payload.get("decision_corrections"))
    loot_corrections = _model_list_to_dicts(output_payload.get("loot_corrections"))
    quote_corrections = _model_list_to_dicts(output_payload.get("quote_corrections"))

    new_entities = _model_list_to_dicts(output_payload.get("new_entities"))
    new_events = _model_list_to_dicts(output_payload.get("new_events"))
    new_decisions = _model_list_to_dicts(output_payload.get("new_decisions"))
    new_loot = _model_list_to_dicts(output_payload.get("new_loot"))
    new_quests = _model_list_to_dicts(output_payload.get("new_quests"))
    new_threads = _model_list_to_dicts(output_payload.get("new_threads"))
    new_quotes = _model_list_to_dicts(output_payload.get("new_quotes"))
    new_combat = _model_list_to_dicts(output_payload.get("new_combat"))
    audit_flags = _model_list_to_dicts(output_payload.get("audit_flags"))

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

                # Phase A: corrections
                for upd in entity_description_updates:
                    entity_id = upd.get("entity_id")
                    description = upd.get("description")
                    if not isinstance(entity_id, int) or not isinstance(description, str):
                        logger.warning("Skipping malformed entity_description_update: %s", upd)
                        continue
                    result = await session.execute(
                        sa.update(Entity)
                        .where(Entity.id == entity_id, Entity.game_id == game_id)
                        .values(description=description, updated_at=sa.func.now())
                    )
                    if _affected_rows(result) > 0:
                        entity_ids_to_embed.add(entity_id)

                for upd in quest_description_updates:
                    quest_id = upd.get("quest_id")
                    description = upd.get("description")
                    if not isinstance(quest_id, int) or not isinstance(description, str):
                        logger.warning("Skipping malformed quest_description_update: %s", upd)
                        continue
                    prev = await session.execute(
                        sa.select(Quest.description)
                        .where(
                            Quest.id == quest_id,
                            Quest.game_id == game_id,
                            Quest.is_deleted == False,  # noqa: E712
                        )
                    )
                    old_description = prev.scalar_one_or_none()
                    if old_description is None:
                        continue
                    session.add(
                        QuestDescriptionHistory(
                            quest_id=quest_id,
                            description=old_description,
                            note_id=audit_note_id,
                        )
                    )
                    result = await session.execute(
                        sa.update(Quest)
                        .where(Quest.id == quest_id, Quest.game_id == game_id)
                        .values(
                            description=description,
                            note_ids=sa.func.array_append(Quest.note_ids, audit_note_id),
                            updated_at=sa.func.now(),
                        )
                    )
                    if _affected_rows(result) > 0:
                        quest_ids_to_embed.add(quest_id)

                for upd in quest_status_updates:
                    quest_id = upd.get("quest_id")
                    status = upd.get("status")
                    if not isinstance(quest_id, int) or status not in {"active", "completed"}:
                        logger.warning("Skipping malformed quest_status_update: %s", upd)
                        continue
                    result = await session.execute(
                        sa.update(Quest)
                        .where(
                            Quest.id == quest_id,
                            Quest.game_id == game_id,
                            Quest.is_deleted == False,  # noqa: E712
                        )
                        .values(
                            status=status,
                            note_ids=sa.func.array_append(Quest.note_ids, audit_note_id),
                            updated_at=sa.func.now(),
                        )
                    )
                    if _affected_rows(result) > 0:
                        quest_ids_to_embed.add(quest_id)

                for upd in thread_resolutions:
                    thread_id = upd.get("thread_id")
                    resolution = upd.get("resolution")
                    if not isinstance(thread_id, int) or not isinstance(resolution, str):
                        logger.warning("Skipping malformed thread_resolution: %s", upd)
                        continue
                    result = await session.execute(
                        sa.update(Thread)
                        .where(
                            Thread.id == thread_id,
                            Thread.game_id == game_id,
                            Thread.is_deleted == False,  # noqa: E712
                            Thread.is_resolved == False,  # noqa: E712
                        )
                        .values(
                            is_resolved=True,
                            resolved_at=sa.func.now(),
                            resolved_by_note_id=audit_note_id,
                            resolution=resolution,
                        )
                    )
                    if _affected_rows(result) > 0:
                        thread_ids_to_embed.add(thread_id)
                    else:
                        logger.warning(
                            "Skipping thread_resolution with no updatable row: game_id=%d thread_id=%d",
                            game_id,
                            thread_id,
                        )

                for upd in thread_text_updates:
                    thread_id = upd.get("thread_id")
                    text = upd.get("text")
                    if not isinstance(thread_id, int) or not isinstance(text, str):
                        logger.warning("Skipping malformed thread_text_update: %s", upd)
                        continue
                    result = await session.execute(
                        sa.update(Thread)
                        .where(
                            Thread.id == thread_id,
                            Thread.game_id == game_id,
                            Thread.is_deleted == False,  # noqa: E712
                        )
                        .values(text=text)
                    )
                    if _affected_rows(result) > 0:
                        thread_ids_to_embed.add(thread_id)

                for upd in event_text_updates:
                    event_id = upd.get("event_id")
                    text = upd.get("text")
                    if not isinstance(event_id, int) or not isinstance(text, str):
                        logger.warning("Skipping malformed event_text_update: %s", upd)
                        continue
                    collision = await session.execute(
                        sa.select(Event.id)
                        .where(
                            Event.game_id == game_id,
                            Event.id != event_id,
                            Event.text == text,
                        )
                        .limit(1)
                    )
                    if collision.scalar_one_or_none() is not None:
                        logger.warning(
                            "Skipping event_text_update due to uniqueness collision: game_id=%d event_id=%d",
                            game_id,
                            event_id,
                        )
                        continue
                    result = await session.execute(
                        sa.update(Event)
                        .where(Event.id == event_id, Event.game_id == game_id)
                        .values(text=text)
                    )
                    if _affected_rows(result) > 0:
                        event_ids_to_embed.add(event_id)

                for upd in decision_corrections:
                    decision_id = upd.get("decision_id")
                    decision_text = upd.get("decision")
                    made_by = upd.get("made_by")
                    if not isinstance(decision_id, int) or not isinstance(decision_text, str):
                        logger.warning("Skipping malformed decision_correction: %s", upd)
                        continue
                    decision_exists = await session.execute(
                        sa.select(Decision.id).where(
                            Decision.id == decision_id,
                            Decision.game_id == game_id,
                        )
                    )
                    if decision_exists.scalar_one_or_none() is None:
                        logger.warning(
                            "Skipping decision_correction for missing decision: game_id=%d decision_id=%d",
                            game_id,
                            decision_id,
                        )
                        continue
                    decision_values: dict[str, Any] = {"decision": decision_text}
                    if isinstance(made_by, str) and made_by:
                        decision_values["made_by"] = made_by
                    result = await session.execute(
                        sa.update(Decision)
                        .where(Decision.id == decision_id, Decision.game_id == game_id)
                        .values(**decision_values)
                    )
                    if _affected_rows(result) > 0:
                        decision_ids_to_embed.add(decision_id)

                for upd in loot_corrections:
                    loot_id = upd.get("loot_id")
                    if not isinstance(loot_id, int):
                        logger.warning("Skipping malformed loot_correction: %s", upd)
                        continue

                    loot_values: dict[str, Any] = {}
                    item_name = upd.get("item_name")
                    acquired_by = upd.get("acquired_by")
                    quest_id = upd.get("quest_id")

                    current_row_result = await session.execute(
                        sa.select(Loot.item_name, Loot.acquired_by)
                        .where(Loot.id == loot_id, Loot.game_id == game_id)
                    )
                    current_row = current_row_result.one_or_none()
                    if current_row is None:
                        continue
                    current_item_name, current_acquired_by = current_row

                    if isinstance(item_name, str) and item_name:
                        loot_values["item_name"] = item_name
                    if isinstance(acquired_by, str) and acquired_by:
                        loot_values["acquired_by"] = acquired_by
                    if isinstance(quest_id, int):
                        q_exists = await session.execute(
                            sa.select(Quest.id).where(
                                Quest.id == quest_id,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                        )
                        if q_exists.scalar_one_or_none() is not None:
                            loot_values["quest_id"] = quest_id

                    if not loot_values:
                        continue

                    next_item_name = loot_values.get("item_name", current_item_name)
                    next_acquired_by = loot_values.get("acquired_by", current_acquired_by)
                    collision = await session.execute(
                        sa.select(Loot.id)
                        .where(
                            Loot.game_id == game_id,
                            Loot.id != loot_id,
                            Loot.item_name == next_item_name,
                            Loot.acquired_by == next_acquired_by,
                        )
                        .limit(1)
                    )
                    if collision.scalar_one_or_none() is not None:
                        logger.warning(
                            "Skipping loot_correction due to uniqueness collision: game_id=%d loot_id=%d",
                            game_id,
                            loot_id,
                        )
                        continue

                    result = await session.execute(
                        sa.update(Loot)
                        .where(Loot.id == loot_id, Loot.game_id == game_id)
                        .values(**loot_values)
                    )
                    if _affected_rows(result) > 0:
                        loot_ids_to_embed.add(loot_id)

                for upd in quote_corrections:
                    quote_id = upd.get("quote_id")
                    if not isinstance(quote_id, int):
                        logger.warning("Skipping malformed quote_correction: %s", upd)
                        continue

                    quote_values: dict[str, Any] = {}
                    text = upd.get("text")
                    speaker = upd.get("speaker")
                    transcript_id = upd.get("transcript_id")

                    if isinstance(text, str) and text:
                        quote_values["text"] = text
                    if speaker is None or isinstance(speaker, str):
                        quote_values["speaker"] = speaker
                    if isinstance(transcript_id, int):
                        transcript_result = await session.execute(
                            sa.select(Transcript.id).where(
                                Transcript.id == transcript_id,
                                Transcript.game_id == game_id,
                            )
                        )
                        if transcript_result.scalar_one_or_none() is not None:
                            quote_values["transcript_id"] = transcript_id
                    elif transcript_id is None:
                        quote_values["transcript_id"] = None

                    if not quote_values:
                        continue
                    await session.execute(
                        sa.update(ImportantQuote)
                        .where(ImportantQuote.id == quote_id, ImportantQuote.game_id == game_id)
                        .values(**quote_values)
                    )

                # Phase B: new data
                for item in new_entities:
                    entity_type = item.get("entity_type")
                    name = item.get("name")
                    description = item.get("description")
                    if (
                        not isinstance(entity_type, str)
                        or not isinstance(name, str)
                        or not isinstance(description, str)
                    ):
                        logger.warning("Skipping malformed new_entity item: %s", item)
                        continue
                    entity_insert_stmt = pg_insert(Entity).values(
                        game_id=game_id,
                        entity_type=entity_type,
                        name=name,
                        description=description,
                    )
                    entity_upsert_stmt = entity_insert_stmt.on_conflict_do_update(
                        constraint="uq_entities_game_entity_type_name",
                        set_={
                            "description": entity_insert_stmt.excluded.description,
                            "updated_at": sa.func.now(),
                        },
                    ).returning(Entity.id)
                    entity_result = await session.execute(entity_upsert_stmt)
                    entity_id = entity_result.scalar_one()
                    entity_ids_to_embed.add(entity_id)
                    await session.execute(
                        pg_insert(notes_entities_table)
                        .values(note_id=audit_note_id, entity_id=entity_id)
                        .on_conflict_do_nothing()
                    )

                for item in new_events:
                    text = item.get("text")
                    if not isinstance(text, str) or not text:
                        logger.warning("Skipping malformed new_event item: %s", item)
                        continue
                    event_stmt = (
                        pg_insert(Event)
                        .values(game_id=game_id, text=text)
                        .on_conflict_do_nothing(constraint="uq_events_game_text")
                        .returning(Event.id)
                    )
                    event_result = await session.execute(event_stmt)
                    event_id = event_result.scalar_one_or_none()
                    if event_id is None:
                        existing = await session.execute(
                            sa.select(Event.id).where(Event.game_id == game_id, Event.text == text)
                        )
                        event_id = existing.scalar_one()
                    event_ids_to_embed.add(event_id)
                    await session.execute(
                        pg_insert(notes_events_table)
                        .values(note_id=audit_note_id, event_id=event_id)
                        .on_conflict_do_nothing()
                    )

                for item in new_decisions:
                    decision_text = item.get("decision")
                    made_by = item.get("made_by")
                    if not isinstance(decision_text, str) or not isinstance(made_by, str):
                        logger.warning("Skipping malformed new_decision item: %s", item)
                        continue
                    decision = Decision(
                        game_id=game_id,
                        note_id=audit_note_id,
                        decision=decision_text,
                        made_by=made_by,
                    )
                    session.add(decision)
                    await session.flush()
                    decision_ids_to_embed.add(decision.id)

                for item in new_loot:
                    item_name = item.get("item_name")
                    acquired_by = item.get("acquired_by")
                    quest_id_raw = item.get("quest_id")
                    if not isinstance(item_name, str) or not isinstance(acquired_by, str):
                        logger.warning("Skipping malformed new_loot item: %s", item)
                        continue

                    loot_quest_id: Optional[int] = None
                    if isinstance(quest_id_raw, int):
                        q_exists = await session.execute(
                            sa.select(Quest.id).where(
                                Quest.id == quest_id_raw,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                        )
                        if q_exists.scalar_one_or_none() is not None:
                            loot_quest_id = quest_id_raw

                    loot_insert_stmt = pg_insert(Loot).values(
                        game_id=game_id,
                        item_name=item_name,
                        acquired_by=acquired_by,
                        quest_id=loot_quest_id,
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
                    loot_result = await session.execute(loot_upsert_stmt)
                    loot_id = loot_result.scalar_one()
                    loot_ids_to_embed.add(loot_id)
                    await session.execute(
                        pg_insert(notes_loot_table)
                        .values(note_id=audit_note_id, loot_id=loot_id)
                        .on_conflict_do_nothing()
                    )

                for item in new_quests:
                    name = item.get("name")
                    description = item.get("description")
                    status = item.get("status", "active")
                    if (
                        not isinstance(name, str)
                        or not isinstance(description, str)
                        or status not in {"active", "completed"}
                    ):
                        logger.warning("Skipping malformed new_quest item: %s", item)
                        continue
                    quest_insert_stmt = pg_insert(Quest).values(
                        game_id=game_id,
                        name=name,
                        description=description,
                        status=status,
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
                            "note_ids": sa.func.array_append(Quest.note_ids, audit_note_id),
                            "updated_at": sa.func.now(),
                            "is_deleted": False,
                            "deleted_at": None,
                            "deleted_reason": None,
                        },
                    ).returning(Quest.id)
                    quest_result = await session.execute(quest_upsert_stmt)
                    quest_id = quest_result.scalar_one()
                    quest_ids_to_embed.add(quest_id)

                # Explicit flush to make all quest inserts/updates visible before threads.
                await session.flush()

                for item in new_threads:
                    text = item.get("text")
                    quest_id_raw = item.get("quest_id")
                    if not isinstance(text, str):
                        logger.warning("Skipping malformed new_thread item: %s", item)
                        continue
                    safe_quest_id: Optional[int] = None
                    if isinstance(quest_id_raw, int):
                        q_exists = await session.execute(
                            sa.select(Quest.id).where(
                                Quest.id == quest_id_raw,
                                Quest.game_id == game_id,
                                Quest.is_deleted == False,  # noqa: E712
                            )
                        )
                        if q_exists.scalar_one_or_none() is not None:
                            safe_quest_id = quest_id_raw
                        else:
                            logger.warning(
                                "Skipping quest link for new thread due to unknown/deleted quest_id=%s",
                                quest_id_raw,
                            )
                    thread = Thread(
                        game_id=game_id,
                        text=text,
                        quest_id=safe_quest_id,
                        opened_by_note_id=audit_note_id,
                    )
                    session.add(thread)
                    await session.flush()
                    thread_ids_to_embed.add(thread.id)

                for item in new_quotes:
                    text = item.get("text")
                    transcript_id = item.get("transcript_id")
                    speaker = item.get("speaker")
                    if not isinstance(text, str):
                        logger.warning("Skipping malformed new_quote item: %s", item)
                        continue
                    safe_transcript_id: Optional[int] = None
                    if isinstance(transcript_id, int):
                        t_exists = await session.execute(
                            sa.select(Transcript.id).where(
                                Transcript.id == transcript_id,
                                Transcript.game_id == game_id,
                            )
                        )
                        if t_exists.scalar_one_or_none() is not None:
                            safe_transcript_id = transcript_id
                    session.add(
                        ImportantQuote(
                            game_id=game_id,
                            note_id=audit_note_id,
                            transcript_id=safe_transcript_id,
                            text=text,
                            speaker=speaker if isinstance(speaker, str) or speaker is None else None,
                        )
                    )

                for item in new_combat:
                    encounter = item.get("encounter")
                    outcome = item.get("outcome")
                    if not isinstance(encounter, str) or not isinstance(outcome, str):
                        logger.warning("Skipping malformed new_combat item: %s", item)
                        continue
                    combat_row = CombatUpdate(
                        game_id=game_id,
                        note_id=audit_note_id,
                        encounter=encounter,
                        outcome=outcome,
                    )
                    session.add(combat_row)
                    await session.flush()
                    combat_ids_to_embed.add(combat_row.id)

                # Phase C: flags + finalize run
                for flag_payload in audit_flags:
                    flag_type = flag_payload.get("flag_type")
                    description = flag_payload.get("description")
                    target_type = flag_payload.get("target_type")
                    target_id = flag_payload.get("target_id")
                    suggested_change = flag_payload.get("suggested_change") or {}

                    if not isinstance(flag_type, str) or not isinstance(description, str):
                        logger.warning("Skipping malformed audit_flag item: %s", flag_payload)
                        continue
                    session.add(
                        AuditFlag(
                            game_id=game_id,
                            audit_run_id=audit_run_id,
                            flag_type=flag_type,
                            target_type=target_type if isinstance(target_type, str) else None,
                            target_id=target_id if isinstance(target_id, int) else None,
                            description=description,
                            suggested_change=suggested_change if isinstance(suggested_change, dict) else {},
                            status="pending",
                        )
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
