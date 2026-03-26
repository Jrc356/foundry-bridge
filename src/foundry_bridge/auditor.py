import asyncio
import contextlib
from dataclasses import dataclass
import logging
import os
import random
from typing import Optional

from langgraph.errors import GraphRecursionError
from sqlalchemy.exc import IntegrityError

from foundry_bridge.audit_generator import generate_audit
from foundry_bridge.db import (
    _write_audit_embeddings,
    complete_audit_run_noop,
    create_audit_run,
    delete_audit_run_if_running,
    embed_unembedded_rows,
    fail_audit_run,
    get_last_audit_run_for_game,
    get_notes_since_last_audit,
    get_player_characters_for_game,
    get_running_audit_run_for_game,
    get_transcripts_for_notes,
    get_unaudited_note_count,
    reset_stale_audit_runs,
    touch_audit_run_heartbeat,
    write_audit_pipeline_result,
)
from foundry_bridge.locks import get_game_lock

logger = logging.getLogger(__name__)

AUDIT_CADENCE_SECONDS = int(os.getenv("AUDIT_CADENCE_SECONDS", "60"))
AUDIT_AFTER_N_NOTES = int(os.getenv("AUDIT_AFTER_N_NOTES", "5"))

_STALE_SWEEP_SECONDS = 5 * 60
_STALE_AFTER_MINUTES = 15
_STARTUP_JITTER_SECONDS = 30
_HEARTBEAT_TICK_SECONDS = 60


@dataclass
class AuditTriggerResult:
    ok: bool
    noop: bool
    reason_code: str
    message: str
    audit_run_id: Optional[int] = None


_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_inflight_tasks: set[asyncio.Task] = set()
_game_tasks: dict[int, asyncio.Task] = {}


def start_background_tasks() -> None:
    """Spawn auditor startup + stale-run sweeper loop."""
    global _task, _stop_event

    if _task is not None and not _task.done():
        logger.debug("Auditor background task already running")
        return

    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_startup_and_poll(), name="auditor:startup")
    logger.info("Auditor background task started (cadence=%ds)", AUDIT_CADENCE_SECONDS)


async def stop_background_tasks() -> None:
    """Stop sweeper loop and cancel in-flight audit tasks."""
    global _task, _stop_event

    if _task is None:
        return

    if _stop_event is not None:
        _stop_event.set()

    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        logger.debug("Auditor background task cancelled")
    finally:
        _task = None
        _stop_event = None

    if _inflight_tasks:
        for t in list(_inflight_tasks):
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*_inflight_tasks, return_exceptions=True)


async def _startup_and_poll() -> None:
    jitter = random.uniform(0, float(_STARTUP_JITTER_SECONDS))
    if jitter > 0:
        logger.info("Auditor startup jitter %.2fs", jitter)
        await asyncio.sleep(jitter)

    try:
        stale_count = await reset_stale_audit_runs(stale_after_minutes=_STALE_AFTER_MINUTES)
        if stale_count:
            logger.warning("Reset %d stale audit runs on startup", stale_count)
    except Exception:
        logger.exception("Failed startup stale-audit reset")

    await _auditor_loop()


async def _auditor_loop() -> None:
    """Periodic stale-audit sweeper loop."""
    next_sweep = 0.0
    while True:
        try:
            if _stop_event is not None and _stop_event.is_set():
                return

            now = asyncio.get_running_loop().time()
            if now >= next_sweep:
                try:
                    await reset_stale_audit_runs(stale_after_minutes=_STALE_AFTER_MINUTES)
                except Exception:
                    logger.exception("Periodic stale-audit sweep failed")
                next_sweep = now + float(_STALE_SWEEP_SECONDS)

            try:
                if _stop_event is None:
                    await asyncio.sleep(AUDIT_CADENCE_SECONDS)
                else:
                    await asyncio.wait_for(_stop_event.wait(), timeout=AUDIT_CADENCE_SECONDS)
            except asyncio.TimeoutError:
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in auditor polling loop")


def _register_task(game_id: int, audit_run_id: int, force: bool) -> bool:
    active = _game_tasks.get(game_id)
    if active is not None and not active.done():
        return False

    task = asyncio.create_task(
        _run_audit_pipeline(game_id=game_id, audit_run_id=audit_run_id, force=force),
        name=f"audit:game:{game_id}:run:{audit_run_id}",
    )
    _game_tasks[game_id] = task
    _inflight_tasks.add(task)

    def _on_done(done: asyncio.Task) -> None:
        _inflight_tasks.discard(done)
        current = _game_tasks.get(game_id)
        if current is done:
            _game_tasks.pop(game_id, None)
        with contextlib.suppress(asyncio.CancelledError):
            exc = done.exception()
            if exc is not None:
                logger.exception(
                    "Unhandled exception in audit task (game_id=%d run_id=%d)",
                    game_id,
                    audit_run_id,
                    exc_info=exc,
                )

    task.add_done_callback(_on_done)
    return True


async def _touch_phase(audit_run_id: int, phase: str) -> None:
    if not await touch_audit_run_heartbeat(audit_run_id):
        logger.warning(
            "Audit heartbeat update skipped (run not running?) run_id=%d phase=%s",
            audit_run_id,
            phase,
        )


async def _await_with_heartbeat(
    *,
    awaitable,
    audit_run_id: int,
    phase: str,
):
    task = asyncio.create_task(awaitable)
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=_HEARTBEAT_TICK_SECONDS)
        except asyncio.TimeoutError:
            await _touch_phase(audit_run_id, f"{phase}:tick")


async def _run_audit_pipeline(game_id: int, audit_run_id: int, force: bool = False) -> None:
    lock = get_game_lock(game_id)
    if lock.locked():
        logger.info(
            "Skipping audit run because game lock is held (game_id=%d run_id=%d)",
            game_id,
            audit_run_id,
        )
        cleaned = await delete_audit_run_if_running(audit_run_id)
        if not cleaned:
            await fail_audit_run(audit_run_id)
        return

    write_started = False
    try:
        async with lock:
            await _touch_phase(audit_run_id, "start")

            await _touch_phase(audit_run_id, "embed_unembedded_rows")
            await _await_with_heartbeat(
                awaitable=embed_unembedded_rows(game_id),
                audit_run_id=audit_run_id,
                phase="embed_unembedded_rows",
            )

            await _touch_phase(audit_run_id, "collect_notes")
            since_note_id = None
            if not force:
                last_run = await get_last_audit_run_for_game(game_id)
                since_note_id = last_run.max_note_id if last_run is not None else None
            notes = await get_notes_since_last_audit(game_id, since_note_id)
            if not notes:
                await complete_audit_run_noop(audit_run_id)
                logger.info(
                    "Audit run completed with no notes (game_id=%d run_id=%d force=%s)",
                    game_id,
                    audit_run_id,
                    force,
                )
                return

            transcripts = await get_transcripts_for_notes([n.id for n in notes])
            player_characters = await get_player_characters_for_game(game_id)

            await _touch_phase(audit_run_id, "generate_audit")
            output = await _await_with_heartbeat(
                awaitable=generate_audit(
                    game_id=game_id,
                    transcripts=transcripts,
                    player_characters=player_characters,
                ),
                audit_run_id=audit_run_id,
                phase="generate_audit",
            )

            write_started = True
            await _touch_phase(audit_run_id, "write_audit_pipeline_result")
            pipeline_result = await _await_with_heartbeat(
                awaitable=write_audit_pipeline_result(
                    game_id=game_id,
                    audit_run_id=audit_run_id,
                    output=output,
                    notes=notes,
                ),
                audit_run_id=audit_run_id,
                phase="write_audit_pipeline_result",
            )

            # write_audit_pipeline_result marks the run as completed; embeddings are
            # post-commit best-effort and should not heartbeat a completed run.
            await _write_audit_embeddings(pipeline_result)
    except GraphRecursionError:
        logger.warning(
            "Audit generation recursion failure; marking run failed (game_id=%d run_id=%d)",
            game_id,
            audit_run_id,
        )
        await fail_audit_run(audit_run_id)
    except Exception:
        logger.exception(
            "Audit pipeline failure (game_id=%d run_id=%d write_started=%s)",
            game_id,
            audit_run_id,
            write_started,
        )
        if not write_started:
            cleaned = await delete_audit_run_if_running(audit_run_id)
            if not cleaned:
                await fail_audit_run(audit_run_id)


async def trigger_audit_run(
    game_id: int,
    *,
    trigger_source: str,
    force: bool = False,
) -> AuditTriggerResult:
    running = await get_running_audit_run_for_game(game_id)
    if running is not None:
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="conflict_running",
            message="An audit run is already in progress for this game",
            audit_run_id=running.id,
        )

    lock = get_game_lock(game_id)
    if lock.locked():
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="conflict_running",
            message="Game pipeline lock is currently held",
            audit_run_id=None,
        )

    unaudited_count = await get_unaudited_note_count(game_id)
    if not force and unaudited_count == 0:
        return AuditTriggerResult(
            ok=True,
            noop=True,
            reason_code="noop_no_new_notes",
            message="No unaudited notes available for this game",
            audit_run_id=None,
        )

    try:
        run = await create_audit_run(game_id=game_id, trigger_source=trigger_source)
    except IntegrityError:
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="conflict_running",
            message="An audit run was created concurrently",
            audit_run_id=None,
        )
    except Exception:
        logger.exception("Failed to pre-create audit run (game_id=%d source=%s)", game_id, trigger_source)
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="precreate_failed",
            message="Failed to create audit run",
            audit_run_id=None,
        )

    if get_game_lock(game_id).locked():
        cleaned = await delete_audit_run_if_running(run.id)
        if not cleaned:
            await fail_audit_run(run.id)
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="early_pipeline_failure",
            message="Pipeline lock became unavailable before audit could start",
            audit_run_id=run.id,
        )

    try:
        if not _register_task(game_id=game_id, audit_run_id=run.id, force=force):
            cleaned = await delete_audit_run_if_running(run.id)
            if not cleaned:
                await fail_audit_run(run.id)
            return AuditTriggerResult(
                ok=False,
                noop=False,
                reason_code="early_pipeline_failure",
                message="Audit pipeline could not start after pre-creation",
                audit_run_id=run.id,
            )
    except Exception:
        logger.exception("Unexpected scheduling failure for audit run (game_id=%d run_id=%d)", game_id, run.id)
        cleaned = await delete_audit_run_if_running(run.id)
        if not cleaned:
            await fail_audit_run(run.id)
        return AuditTriggerResult(
            ok=False,
            noop=False,
            reason_code="schedule_failed",
            message="Failed to schedule audit run",
            audit_run_id=run.id,
        )

    return AuditTriggerResult(
        ok=True,
        noop=False,
        reason_code="scheduled",
        message="Audit run scheduled",
        audit_run_id=run.id,
    )


async def trigger_manual_audit(game_id: int, force: bool = False) -> AuditTriggerResult:
    return await trigger_audit_run(game_id, trigger_source="manual", force=force)


async def maybe_schedule_auto_audit(game_id: int) -> AuditTriggerResult:
    unaudited_count = await get_unaudited_note_count(game_id)
    if unaudited_count < AUDIT_AFTER_N_NOTES:
        return AuditTriggerResult(
            ok=True,
            noop=True,
            reason_code="noop_below_threshold",
            message=(
                f"Unaudited note count {unaudited_count} is below threshold {AUDIT_AFTER_N_NOTES}"
            ),
            audit_run_id=None,
        )
    return await trigger_audit_run(game_id, trigger_source="auto", force=False)
