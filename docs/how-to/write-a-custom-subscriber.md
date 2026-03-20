# How to write a custom subscriber

This guide shows you how to build a custom foundry-bridge subscriber that connects to the bridge server and processes incoming audio frames and lifecycle events.

## Prerequisites

- foundry-bridge installed (`uv sync`)
- A running bridge server

## Step 1: Create a new Python file

Create a file for your subscriber, for example `my_subscriber.py`.

## Step 2: Subclass BaseSubscriber

Import `BaseSubscriber` and define your class. Pass a bridge WebSocket URI and a descriptive name to the constructor:

```python
import asyncio
from typing import Any

from foundry_bridge.subscriber import BaseSubscriber


class MySubscriber(BaseSubscriber):
    def __init__(self) -> None:
        super().__init__(uri="ws://127.0.0.1:8765", name="my-subscriber")
```

## Step 3: Implement on_audio_frame

`on_audio_frame` is the only required method. It is called for every complete audio frame received from the bridge. `header` is a dict containing participant metadata and audio format details; `data` is the raw PCM16-LE bytes.

```python
    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        participant = header["name"]
        sample_rate = header["sampleRate"]
        print(f"{participant}: {len(data)} bytes at {sample_rate} Hz")
```

Refer to the [WebSocket protocol reference](../reference/websocket-protocol.md) for all fields available in `header`.

## Step 4: Implement on_event (optional)

Override `on_event` to handle lifecycle events such as participants joining or leaving:

```python
    async def on_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "participant_attached":
            print(f"Participant joined: {event.get('name')}")
        elif event_type == "participant_detached":
            print(f"Participant left: {event.get('participantId')}")
```

If you do not override `on_event`, the base class silently discards non-audio events.

## Step 5: Add a main entry point

```python
def main() -> None:
    try:
        asyncio.run(MySubscriber().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

## Step 6: Run your subscriber

```bash
python my_subscriber.py
```

The subscriber will connect to the bridge, complete the handshake, and begin receiving audio frames as soon as the userscript starts capturing.

## Using BRIDGE_URI from the environment

To make the bridge URI configurable without code changes:

```python
import os

URI = os.getenv("BRIDGE_URI", "ws://127.0.0.1:8765")

class MySubscriber(BaseSubscriber):
    def __init__(self) -> None:
        super().__init__(uri=URI, name="my-subscriber")
```

## Related

- [BaseSubscriber API reference](../reference/base-subscriber-api.md) — full method signatures and behaviour
- [WebSocket protocol reference](../reference/websocket-protocol.md) — audio frame header fields and lifecycle events
- [`src/foundry_bridge/subscribers/example.py`](../../src/foundry_bridge/subscribers/example.py) — minimal reference implementation
