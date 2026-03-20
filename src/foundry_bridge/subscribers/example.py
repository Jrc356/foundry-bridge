import asyncio
import os
from typing import Any

from foundry_bridge.subscriber import BaseSubscriber


URI = os.getenv("BRIDGE_URI", "ws://127.0.0.1:8765")


class ExampleSubscriber(BaseSubscriber):
    def __init__(self) -> None:
        super().__init__(uri=URI, name="debug-consumer")

    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        print(
            "audio:",
            header["name"],
            header["participantId"],
            header["sampleRate"],
            header["samples"],
            len(data),
            "bytes",
        )

    async def on_event(self, event: dict[str, Any]) -> None:
        print("json:", event)


def main() -> None:
    try:
        asyncio.run(ExampleSubscriber().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
