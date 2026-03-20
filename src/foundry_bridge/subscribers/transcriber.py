import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from websockets.exceptions import ConnectionClosed

from foundry_bridge.subscriber import BaseSubscriber


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BRIDGE_URI = os.getenv("BRIDGE_URI", "ws://127.0.0.1:8765")
DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
if not DEEPGRAM_API_KEY:
    raise ValueError("DEEPGRAM_API_KEY environment variable is required")

dg_client = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)


@dataclass
class SpeakerWorker:
    participant_id: str
    label: str
    sample_rate: int
    channels: int
    queue: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task[None]] = None


def transcript_text_from_message(message: Any) -> str:
    try:
        channel = getattr(message, "channel", None)
        if not channel:
            return ""
        alternatives = getattr(channel, "alternatives", None)
        if not alternatives:
            return ""
        first = alternatives[0]
        return getattr(first, "transcript", "") or ""
    except Exception:
        return ""


async def speaker_loop(worker: SpeakerWorker) -> None:
    label = worker.label

    try:
        async with dg_client.listen.v2.connect(
            model="flux-general-en",
            encoding="linear16",
            sample_rate=f"{worker.sample_rate}",
        ) as connection:
            def on_open(_: Any) -> None:
                logging.info("[%s] Deepgram connection opened", label)

            def on_close(_: Any) -> None:
                logging.info("[%s] Deepgram connection closed", label)

            def on_error(error: Any) -> None:
                logging.warning("[%s] Deepgram error: %s", label, error)

            def on_message(message: Any) -> None:
                msg_type = getattr(message, "type", "Unknown")

                if msg_type == "Results":
                    transcript = transcript_text_from_message(message)
                    is_final = getattr(message, "is_final", False)
                    speech_final = getattr(message, "speech_final", False)

                    if transcript.strip():
                        logging.info(
                            "[%s] final=%s speech_final=%s transcript=%s",
                            label,
                            is_final,
                            speech_final,
                            transcript.strip(),
                        )
                elif msg_type == "SpeechStarted":
                    logging.info("[%s] speech started", label)
                elif msg_type == "UtteranceEnd":
                    logging.info("[%s] utterance end", label)

            connection.on(EventType.OPEN, on_open)
            connection.on(EventType.MESSAGE, on_message)
            connection.on(EventType.CLOSE, on_close)
            connection.on(EventType.ERROR, on_error)

            listen_task = asyncio.create_task(connection.start_listening())

            try:
                while True:
                    chunk = await worker.queue.get()
                    if chunk == b"":
                        break
                    await connection.send_media(chunk)
            finally:
                with contextlib.suppress(Exception):
                    await connection.send_close_stream()

                listen_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listen_task

    except Exception as exc:
        logging.exception("[%s] speaker loop failed: %s", label, exc)


class TranscriberSubscriber(BaseSubscriber):
    def __init__(self) -> None:
        super().__init__(uri=BRIDGE_URI, name="deepgram-transcriber")
        self._speaker_workers: dict[str, SpeakerWorker] = {}

    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        participant_id = str(header["participantId"])
        label = (
            header.get("characterName")
            or header.get("label")
            or header.get("name")
            or participant_id
        )
        sample_rate = int(header.get("sampleRate", 48000))
        channels = int(header.get("channels", 1))

        worker = await self._ensure_speaker_worker(
            participant_id=participant_id,
            label=str(label),
            sample_rate=sample_rate,
            channels=channels,
        )
        await worker.queue.put(data)

    async def on_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")

        if event_type == "ingest_event":
            inner = event.get("event", {})
            if inner.get("type") == "participant_detached":
                participant_id = inner.get("participantId")
                if participant_id:
                    await self._close_speaker_worker(participant_id)

    async def _ensure_speaker_worker(
        self,
        participant_id: str,
        label: str,
        sample_rate: int,
        channels: int,
    ) -> SpeakerWorker:
        existing = self._speaker_workers.get(participant_id)
        if existing is not None:
            return existing

        worker = SpeakerWorker(
            participant_id=participant_id,
            label=label,
            sample_rate=sample_rate,
            channels=channels,
        )
        worker.task = asyncio.create_task(speaker_loop(worker))
        self._speaker_workers[participant_id] = worker
        logging.info("Started worker for %s (%s)", label, participant_id)
        return worker

    async def _close_speaker_worker(self, participant_id: str) -> None:
        worker = self._speaker_workers.pop(participant_id, None)
        if worker is None:
            return

        await worker.queue.put(b"")

        if worker.task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await worker.task

        logging.info("Stopped worker for %s (%s)", worker.label, participant_id)

    async def _shutdown_all_workers(self) -> None:
        await asyncio.gather(
            *(self._close_speaker_worker(pid) for pid in list(self._speaker_workers.keys())),
            return_exceptions=True,
        )


async def _run() -> None:
    subscriber = TranscriberSubscriber()
    try:
        await subscriber.run()
    except ConnectionClosed:
        logging.info("Bridge connection closed")
    finally:
        await subscriber._shutdown_all_workers()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
