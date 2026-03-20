# WebSocket protocol

All WebSocket messages use either JSON text frames or binary frames. All JSON messages include a `type` field.

The bridge listens on port `8765` by default.

## Handshake

Both ingest and subscriber clients must send a `hello` message immediately after connecting.

### hello (client → server)

```json
{
  "type": "hello",
  "role": "ingest" | "subscriber",
  "name": "<string>"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | Must be `"hello"` |
| `role` | string | `"ingest"` for audio sources; `"subscriber"` for consumers |
| `name` | string | Human-readable identifier for this client (used in logs) |

### hello_ack (server → client)

```json
{
  "type": "hello_ack",
  "role": "ingest" | "subscriber",
  "clientId": "<string>"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"hello_ack"` |
| `role` | string | The role that was acknowledged |
| `clientId` | string | Server-assigned opaque identifier for this connection |

## Audio frames

Audio is transmitted as two consecutive WebSocket messages. This applies to both the ingest path (userscript → server) and the subscriber path (server → subscriber).

### Ingest audio message (userscript → server)

The userscript sends a JSON text frame:

```json
{
  "type": "audio",
  "participantId": "<string>",
  "name": "<string>",
  "sampleRate": 48000,
  "channels": 1,
  "samples": 4096,
  "ts": 1700000000000
}
```

Immediately followed by a binary WebSocket frame containing raw PCM16-LE audio data.

### audio_frame_header (server → subscriber)

The server re-wraps and forwards the audio to all subscribers as two consecutive messages.

**Message 1 — JSON header:**

```json
{
  "type": "audio_frame_header",
  "clientId": "<string>",
  "participantId": "<string>",
  "name": "<string>",
  "sampleRate": 48000,
  "channels": 1,
  "samples": 4096,
  "ts": 1700000000000,
  "encoding": "pcm_s16le",
  "byteLength": 8192
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | Always `"audio_frame_header"` |
| `clientId` | string | Server-assigned ID of the ingest connection that sent this frame |
| `participantId` | string | Foundry VTT user ID of the participant |
| `name` | string | Display name of the participant |
| `sampleRate` | integer | Sample rate in Hz (typically `48000`) |
| `channels` | integer | Number of audio channels (always `1` — mono) |
| `samples` | integer | Number of samples in this frame (typically `4096`) |
| `ts` | integer | Millisecond timestamp from the capturing browser |
| `encoding` | string | Always `"pcm_s16le"` — signed 16-bit little-endian PCM |
| `byteLength` | integer | Byte length of the binary frame that follows (`samples × channels × 2`) |

**Message 2 — Binary frame:**

Raw PCM16-LE audio bytes, exactly `byteLength` bytes long.

## Lifecycle events

Lifecycle events are JSON-only messages (no associated binary frame). They are broadcast to all subscriber clients.

| `type` | Direction | Description |
|---|---|---|
| `bridge_connection_opened` | server → subscribers | A new ingest or subscriber client connected |
| `bridge_connection_closed` | server → subscribers | A client disconnected |
| `participant_attached` | ingest → subscribers | Audio capture started for a participant |
| `participant_detached` | ingest → subscribers | Audio capture stopped for a participant |
| `capture_started` | ingest → subscribers | The userscript started a capture session |
| `capture_stopped` | ingest → subscribers | The userscript stopped a capture session |

All lifecycle events include at minimum a `type` field. `participant_attached` and `participant_detached` also include `participantId` and `name`.

## See also

- [BaseSubscriber API](./base-subscriber-api.md) — the `on_audio_frame` and `on_event` callbacks
- [How to write a custom subscriber](../how-to/write-a-custom-subscriber.md) — receiving these messages in practice
