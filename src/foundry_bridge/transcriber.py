import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v2.types import ListenV2TurnInfo

from foundry_bridge.db import get_keyterms_for_game, store_transcript

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_EOT_TIMEOUT_MS: str = os.environ.get("DEEPGRAM_EOT_TIMEOUT_MS", "3000")

# Module-level reconnect constants
RECONNECT_INITIAL_DELAY: float = 1.0   # seconds
RECONNECT_MAX_DELAY: float = 30.0      # seconds
RECONNECT_MAX_RETRIES: int = 5

_dg_client: Optional[AsyncDeepgramClient] = None
_speaker_workers: dict[str, "SpeakerWorker"] = {}


@dataclass
class SpeakerWorker:
    participant_id: str
    label: str
    sample_rate: int
    channels: int
    game_id: int
    keyterms: list[str] = field(default_factory=list)
    queue: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task] = None
    turn_started_at: Optional[datetime] = None


async def init() -> None:
    """Validate config and initialise the Deepgram client. Called once by server.py."""
    global _dg_client
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY is not set")
    _dg_client = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)
    logger.info("Transcriber initialised")


async def shutdown() -> None:
    """Gracefully drain all speaker workers (call from server shutdown)."""
    await asyncio.gather(
        *(_close_speaker_worker(pid) for pid in list(_speaker_workers.keys())),
        return_exceptions=True,
    )
    logger.info("Transcriber shut down")


async def handle_event(event: dict[str, Any]) -> None:
    """Called by server.py for non-audio ingest events."""
    if event.get("type") == "participant_detached":
        participant_id = event.get("participantId")
        if participant_id:
            logger.info("Participant detached: %s", participant_id)
            await _close_speaker_worker(str(participant_id))


async def handle_audio_frame(header: dict[str, Any], data: bytes, *, game_id: int) -> None:
    """Called by server.py for every ingest audio frame."""
    if _dg_client is None:
        return

    participant_id = str(header["participantId"])
    character_name = str(header["character_name"])
    sample_rate = int(header.get("sampleRate", 48000))
    channels = int(header.get("channels", 1))

    worker = await _ensure_speaker_worker(
        participant_id=participant_id,
        label=character_name,
        sample_rate=sample_rate,
        channels=channels,
        game_id=game_id,
    )
    logger.debug(
        "Audio frame queued: char=%s game_id=%d bytes=%d",
        character_name, game_id, len(data),
    )
    await worker.queue.put(data)


async def _ensure_speaker_worker(
    participant_id: str,
    label: str,
    sample_rate: int,
    channels: int,
    game_id: int,
) -> SpeakerWorker:
    existing = _speaker_workers.get(participant_id)
    if existing is not None:
        return existing

    keyterms = await get_keyterms_for_game(game_id)
    worker = SpeakerWorker(
        participant_id=participant_id,
        label=label,
        sample_rate=sample_rate,
        channels=channels,
        game_id=game_id,
        keyterms=keyterms,
    )
    worker.task = asyncio.create_task(_speaker_loop(worker))
    _speaker_workers[participant_id] = worker
    logger.info(
        "Started speaker worker for %s (%s) with %d keyterms",
        label, participant_id, len(keyterms),
    )
    return worker


async def _close_speaker_worker(participant_id: str) -> None:
    worker = _speaker_workers.pop(participant_id, None)
    if worker is None:
        return
    await worker.queue.put(b"")
    if worker.task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await worker.task
    logger.info("Stopped speaker worker for %s (%s)", worker.label, participant_id)


async def _speaker_loop(worker: SpeakerWorker) -> None:
    """Run the Deepgram streaming loop with exponential-backoff retry.

    On unexpected connection failure, retries up to RECONNECT_MAX_RETRIES times
    with initial delay of 1s, doubling each attempt, capped at 30s. After max
    retries, logs an error and exits — the worker is treated as dead and
    subsequent audio frames are dropped until a new worker is created on
    participant reconnect.

    Exits cleanly when the sentinel (b"") is received on the queue.
    """
    label = worker.label
    assert _dg_client is not None

    attempt = 0

    while True:
        try:
            await _speaker_loop_once(worker)
            return  # clean exit via sentinel
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            attempt += 1
            if attempt > RECONNECT_MAX_RETRIES:
                logger.error(
                    "[%s] Deepgram connection failed after %d attempts, giving up: %s",
                    label, RECONNECT_MAX_RETRIES, exc,
                )
                # Remove from dict so the next audio frame creates a fresh worker.
                _speaker_workers.pop(worker.participant_id, None)
                return
            delay = min(RECONNECT_INITIAL_DELAY * (2 ** (attempt - 1)), RECONNECT_MAX_DELAY)
            logger.warning(
                "[%s] Deepgram connection failed (attempt %d/%d), retrying in %.1fs: %s",
                label, attempt, RECONNECT_MAX_RETRIES, delay, exc,
            )
            await asyncio.sleep(delay)


async def _speaker_loop_once(worker: SpeakerWorker) -> None:
    """Single attempt at the Deepgram streaming loop. Raises on unexpected failure."""
    label = worker.label
    assert _dg_client is not None

    worker.turn_started_at = None

    async with _dg_client.listen.v2.connect(
        model="flux-general-en",
        encoding="linear16",
        sample_rate=f"{worker.sample_rate}",
        eot_timeout_ms=DEEPGRAM_EOT_TIMEOUT_MS,
        keyterm=worker.keyterms or None,
    ) as connection:
        def on_open(_: Any) -> None:
            logger.debug("[%s] Deepgram connection opened", label)

        def on_close(_: Any) -> None:
            logger.debug("[%s] Deepgram connection closed", label)

        def on_error(error: Any) -> None:
            logger.warning("[%s] Deepgram error: %s", label, error)

        async def on_message(message: Any) -> None:
            if isinstance(message, ListenV2TurnInfo):
                transcript = getattr(message, "transcript", "") or ""
                event_name = getattr(message, "event", "")
                if transcript.strip():
                    logger.debug(
                        "[%s] event=%s turn=%s confidence=%.2f transcript=%s",
                        label, event_name,
                        getattr(message, "turn_index", "?"),
                        float(getattr(message, "end_of_turn_confidence", 0.0)),
                        transcript.strip(),
                    )
                if event_name == "EndOfTurn" and transcript.strip():
                    # SDK natively supports async callbacks (awaits the return value).
                    # Swallow DB errors so a store failure doesn't trigger a Deepgram reconnect.
                    try:
                        started_at = worker.turn_started_at or datetime.now(timezone.utc)
                        worker.turn_started_at = None
                        await store_transcript(
                            participant_id=worker.participant_id,
                            character_name=worker.label,
                            game_id=worker.game_id,
                            turn_index=int(getattr(message, "turn_index", 0)),
                            text=transcript.strip(),
                            audio_window_start=float(getattr(message, "audio_window_start", 0.0)),
                            audio_window_end=float(getattr(message, "audio_window_end", 0.0)),
                            end_of_turn_confidence=float(getattr(message, "end_of_turn_confidence", 0.0)),
                            started_at=started_at,
                        )
                    except Exception:
                        logger.exception("[%s] Failed to store transcript; dropping turn", label)

        connection.on(EventType.OPEN, on_open)
        connection.on(EventType.MESSAGE, on_message)
        connection.on(EventType.CLOSE, on_close)
        connection.on(EventType.ERROR, on_error)

        listen_task = asyncio.create_task(connection.start_listening())

        try:
            while True:
                chunk = await worker.queue.get()
                if chunk == b"":
                    return  # clean sentinel exit
                if worker.turn_started_at is None:
                    worker.turn_started_at = datetime.now(timezone.utc)
                await connection.send_media(chunk)
        finally:
            with contextlib.suppress(Exception):
                await connection.send_close_stream()
            listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listen_task
