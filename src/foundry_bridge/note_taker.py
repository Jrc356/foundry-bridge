import asyncio
import logging
import os
import re
from datetime import datetime

from langgraph.errors import GraphRecursionError

from foundry_bridge.db import (
    _get_embed_model,
    _write_embeddings_for_pipeline_result,
    embed_unembedded_rows,
    get_game_ids_with_unprocessed_transcripts,
    get_player_characters_for_game,
    get_recent_notes_for_game,
    get_unprocessed_transcripts_for_game,
    upsert_player_characters,
    write_note_pipeline_result,
)
from foundry_bridge.note_generator import generate_note, validate_config

logger = logging.getLogger(__name__)

NOTE_CADENCE_MINUTES = int(os.getenv("NOTE_CADENCE_MINUTES", "10"))
RECENT_NOTES_LIMIT = int(os.getenv("RECENT_NOTES_LIMIT", "3"))

# Per-game asyncio locks; never evicted.
_game_locks: dict[int, asyncio.Lock] = {}
_task: asyncio.Task | None = None
_inflight_tasks: set[asyncio.Task] = set()
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def start_background_tasks() -> None:
    """Spawn the polling loop and pre-load the FastEmbed model."""
    global _task
    _task = asyncio.create_task(_startup_and_poll())
    logger.info("Note taker background task started (cadence=%dm)", NOTE_CADENCE_MINUTES)


async def _startup_and_poll() -> None:
    """Pre-load the FastEmbed ONNX model, validate LLM config, then start the polling loop."""
    await asyncio.to_thread(_get_embed_model)  # blocks ~270 MB disk read off the event loop
    logger.info("FastEmbed model loaded, starting polling loop")
    validate_config()  # fail fast if API key is missing, after model is confirmed loadable
    await _polling_loop()


async def stop_background_tasks() -> None:
    """Cancel the polling loop; await in-flight tasks up to 60 s, then force-cancel."""
    if _task is not None:
        _task.cancel()
    if _inflight_tasks:
        logger.info("Waiting for %d in-flight pipeline tasks to complete...", len(_inflight_tasks))
        try:
            await asyncio.wait_for(
                asyncio.gather(*_inflight_tasks, return_exceptions=True),
                timeout=60.0,
            )
            logger.info("All pipeline tasks completed.")
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout exceeded; force-cancelling remaining pipeline tasks.")
            for t in list(_inflight_tasks):
                t.cancel()


# ── Polling loop ───────────────────────────────────────────────────────────────

async def _polling_loop() -> None:
    while True:
        try:
            poll_time = datetime.now().isoformat()
            game_ids = await get_game_ids_with_unprocessed_transcripts()
            locked_games = []
            
            logger.info("[%s] Poll cycle: %d game(s) with unprocessed transcripts", poll_time, len(game_ids))
            
            for gid in game_ids:
                lock = _game_locks.setdefault(gid, asyncio.Lock())
                if lock.locked():
                    locked_games.append(gid)
                    continue
                t = asyncio.create_task(_run_pipeline_locked(gid, lock))
                _inflight_tasks.add(t)
                t.add_done_callback(_inflight_tasks.discard)
            
            if locked_games:
                logger.info("[%s] Skipped %d game(s) due to in-progress pipelines: %s", poll_time, len(locked_games), locked_games)
        except Exception:
            logger.exception("Error in note taker polling loop")
        next_poll_seconds = NOTE_CADENCE_MINUTES * 60
        logger.debug("Sleeping %d seconds until next poll", next_poll_seconds)
        await asyncio.sleep(next_poll_seconds)


async def _run_pipeline_locked(game_id: int, lock: asyncio.Lock) -> None:
    async with lock:
        try:
            await _run_pipeline(game_id)
        except Exception:
            logger.exception("Pipeline error for game %d", game_id)


# ── Pipeline ───────────────────────────────────────────────────────────────────

async def _run_pipeline(game_id: int) -> None:
    transcripts = await get_unprocessed_transcripts_for_game(game_id)
    if not transcripts:
        return

    # Filter out UUID-like character names (fallback from server.py)
    pc_names = list(set(
        t.character_name for t in transcripts
        if t.character_name and not _UUID_RE.match(t.character_name)
    ))
    await upsert_player_characters(game_id, pc_names)
    player_characters = await get_player_characters_for_game(game_id)

    recent_notes = await get_recent_notes_for_game(game_id, limit=RECENT_NOTES_LIMIT)

    # Step 0: Catch-up — ensure all existing rows have embeddings before agent searches
    await embed_unembedded_rows(game_id)

    start_time = datetime.now().isoformat()
    logger.info(
        "[%s] Starting LLM pipeline for game %d (%d transcripts, %d recent notes)",
        start_time, game_id, len(transcripts), len(recent_notes),
    )
    logger.debug("PC names for game %d: %s", game_id, pc_names if pc_names else "(none filtered from transcripts)")

    try:
        note_output = await generate_note(
            game_id=game_id,
            transcripts=transcripts,
            recent_notes=recent_notes,
            player_characters=player_characters,
        )
    except GraphRecursionError:
        logger.warning(
            "Note generation aborted (recursion limit) for game %d; will retry on next poll",
            game_id,
        )
        return  # transcripts NOT marked processed — will retry

    source_ids = [t.id for t in transcripts]
    # Coerce thread_resolutions keys from str to int (JSON only supports string keys)
    thread_resolutions_int = {int(k): v for k, v in note_output.thread_resolutions.items() if k.isdigit()}
    pipeline_result = await write_note_pipeline_result(
        game_id=game_id,
        note_summary=note_output.summary,
        source_transcript_ids=source_ids,
        entities=[e.model_dump(mode="json") for e in note_output.entities],
        threads_opened=note_output.threads_opened,
        threads_closed=[
            {"id": tid, "resolution": thread_resolutions_int.get(tid, "")}
            for tid in note_output.threads_closed
        ],
        events=note_output.events,
        decisions=[d.model_dump() for d in note_output.decisions],
        loot=[item.model_dump() for item in note_output.loot],
        combat_updates=[c.model_dump() for c in note_output.combat_updates],
        important_quotes=[q.model_dump() for q in note_output.important_quotes],
    )
    await _write_embeddings_for_pipeline_result(pipeline_result)
    end_time = datetime.now().isoformat()
    logger.info("[%s] Note stored for game %d (completion time: %s)", end_time, game_id, end_time)
