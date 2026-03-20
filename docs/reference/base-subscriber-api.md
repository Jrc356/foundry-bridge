# BaseSubscriber API

`BaseSubscriber` is the abstract base class for all bridge subscriber implementations. It handles the WebSocket connection, the `hello`/`hello_ack` handshake, and the audio-frame dispatch loop. Subclasses implement only the methods specific to their use case.

**Module**: `foundry_bridge.subscriber`

## Class signature

```python
class BaseSubscriber(ABC):
    def __init__(self, uri: str, name: str) -> None: ...
```

## Constructor

```python
BaseSubscriber(uri: str, name: str)
```

| Parameter | Type | Description |
|---|---|---|
| `uri` | `str` | WebSocket URI of the bridge server (e.g. `"ws://127.0.0.1:8765"`) |
| `name` | `str` | Human-readable identifier sent in the `hello` handshake; appears in bridge server logs |

## Methods

### run

```python
async def run(self) -> None
```

Connects to the bridge at `self.uri`, sends the `hello` subscriber handshake, and dispatches incoming messages to `on_audio_frame`, `on_event`, or `on_orphan_binary` until the connection closes.

This is the entry point for running the subscriber. It is not meant to be overridden; override the dispatch methods instead.

Raises `websockets.exceptions.ConnectionClosed` (and its subclasses) if the connection closes unexpectedly. Does not reconnect automatically.

---

### on_audio_frame *(abstract)*

```python
@abstractmethod
async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None
```

Called for each complete audio frame (header + binary payload).

| Parameter | Type | Description |
|---|---|---|
| `header` | `dict[str, Any]` | The `audio_frame_header` JSON object. See [WebSocket protocol](./websocket-protocol.md) for all fields. |
| `data` | `bytes` | Raw PCM16-LE audio bytes (`header["byteLength"]` bytes long) |

Must be overridden by all concrete subclasses.

---

### on_event

```python
async def on_event(self, event: dict[str, Any]) -> None
```

Called for every non-audio JSON message received from the bridge, including all lifecycle events.

| Parameter | Type | Description |
|---|---|---|
| `event` | `dict[str, Any]` | The parsed JSON object. Always includes a `type` field. |

Default implementation is a no-op. Override to handle lifecycle events. See [WebSocket protocol — lifecycle events](./websocket-protocol.md#lifecycle-events) for the full list of event types.

---

### on_orphan_binary

```python
async def on_orphan_binary(self, data: bytes) -> None
```

Called if a binary WebSocket frame arrives from the bridge without a preceding `audio_frame_header` JSON message.

| Parameter | Type | Description |
|---|---|---|
| `data` | `bytes` | The unexpected binary payload |

Default implementation logs a warning. Override to handle or suppress this condition.

## Example

```python
import asyncio
import os
from typing import Any
from foundry_bridge.subscriber import BaseSubscriber

class MySubscriber(BaseSubscriber):
    def __init__(self) -> None:
        uri = os.getenv("BRIDGE_URI", "ws://127.0.0.1:8765")
        super().__init__(uri=uri, name="my-subscriber")

    async def on_audio_frame(self, header: dict[str, Any], data: bytes) -> None:
        print(f"{header['name']}: {len(data)} bytes")

    async def on_event(self, event: dict[str, Any]) -> None:
        print(f"Event: {event['type']}")

asyncio.run(MySubscriber().run())
```

## See also

- [WebSocket protocol](./websocket-protocol.md) — message format details
- [How to write a custom subscriber](../how-to/write-a-custom-subscriber.md)
- [`src/foundry_bridge/subscribers/example.py`](../../src/foundry_bridge/subscribers/example.py) — minimal reference implementation
