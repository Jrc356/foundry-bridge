import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from websockets.asyncio.client import connect


class BaseSubscriber(ABC):
    """Abstract base class for bridge subscribers.

    Handles the connect/hello handshake and the audio-frame dispatch loop so
    that concrete subclasses only need to implement what's unique to them.
    """

    def __init__(self, uri: str, name: str) -> None:
        self.uri = uri
        self.name = name

    async def run(self) -> None:
        """Connect to the bridge and dispatch messages until the connection closes."""
        async with connect(self.uri, max_size=None) as ws:
            await ws.send(json.dumps({
                "type": "hello",
                "role": "subscriber",
                "name": self.name,
            }))

            pending_audio_header: Optional[dict[str, Any]] = None

            async for message in ws:
                if isinstance(message, str):
                    event = json.loads(message)

                    if event.get("type") == "audio_frame_header":
                        pending_audio_header = event
                    else:
                        await self.on_event(event)
                else:
                    if pending_audio_header is None:
                        await self.on_orphan_binary(message)
                        continue

                    header = pending_audio_header
                    pending_audio_header = None
                    await self.on_audio_frame(header, message)

    @abstractmethod
    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        """Called for each complete audio frame (header + binary payload)."""

    async def on_event(self, event: dict[str, Any]) -> None:
        """Called for every non-audio JSON event. Override to handle events."""

    async def on_orphan_binary(self, data: bytes) -> None:
        """Called when binary arrives without a preceding audio header."""
        logging.warning(
            "[%s] Received binary from bridge with no pending header (%d bytes)",
            self.name,
            len(data),
        )
