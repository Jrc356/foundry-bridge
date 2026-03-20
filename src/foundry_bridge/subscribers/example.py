import asyncio
import logging
import os
from typing import Any

from foundry_bridge.subscriber import BaseSubscriber


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

URI = os.getenv("BRIDGE_URI", "ws://127.0.0.1:8765")


class ExampleSubscriber(BaseSubscriber):
    def __init__(self) -> None:
        super().__init__(uri=URI, name="debug-consumer")

    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        logging.info(
            "Received audio frame from %s (participant=%s, sampleRate=%s, samples=%s, bytes=%d)",
            header.get("name", "unknown"),
            header.get("participantId"),
            header.get("sampleRate"),
            header.get("samples"),
            len(data),
        )

    async def on_event(self, event: dict[str, Any]) -> None:
        logging.info("Received event: %s", event)


def main() -> None:
    try:
        asyncio.run(ExampleSubscriber().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
