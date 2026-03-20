# foundry-bridge

A WebSocket bridge that captures per-participant audio from [Foundry VTT](https://foundryvtt.com/)'s LiveKit voice chat and streams it to any number of subscribers (e.g. for transcription, recording, or processing).

## How it works

```
Foundry VTT (browser)
   └── userscript.js  ──[WebSocket / PCM16]──▶  main.py bridge  ──▶  subscriber clients
         (ingest)                                                      (e.g. transcribers)
```

1. **`userscript.js`** runs inside the Foundry VTT tab via a userscript manager (Tampermonkey / Violentmonkey). It taps into the LiveKit client, captures each participant's audio track, converts it to raw PCM16, and forwards it over WebSocket to the bridge.
2. **`main.py`** is the bridge server. It accepts two kinds of WebSocket connections:
   - **ingest** – the userscript; sends audio frames and lifecycle events.
   - **subscriber** – downstream consumers; receive every audio frame and event broadcast from all ingest clients.

## Requirements

- Python ≥ 3.10
- [`websockets`](https://websockets.readthedocs.io/) ≥ 16.0
- A userscript manager extension (Tampermonkey, Violentmonkey, etc.)

## Setup

### 1. Install Python dependencies

```bash
uv sync
# or
pip install -e .
```

### 2. Start the bridge

```bash
uv run main.py
# or
python main.py
```

The server listens on `0.0.0.0:8765` by default.

### 3. Install the userscript

Install `userscript.js` via your userscript manager. It matches:

- `https://*.forge-vtt.com/*`
- `https://*.forge-vtt.net/*`
- `http://localhost:30000/*`

Open Foundry VTT in your browser. A control panel will appear in the top-right corner. Enter the bridge WebSocket URL (default: `ws://127.0.0.1:8765`), then click **Connect** and **Start Capture**.

## WebSocket protocol

All JSON messages have a `type` field.

### Handshake (both roles)

Send a `hello` message after connecting:

```json
{ "type": "hello", "role": "ingest" }
{ "type": "hello", "role": "subscriber" }
```

The server replies with:

```json
{ "type": "hello_ack", "role": "...", "clientId": "..." }
```

### Audio frames (ingest → server → subscribers)

Ingest clients send a JSON header followed immediately by a binary WebSocket frame containing the raw PCM16-LE samples:

```json
{
  "type": "audio",
  "participantId": "...",
  "name": "Alice",
  "sampleRate": 48000,
  "channels": 1,
  "samples": 4096,
  "ts": 1700000000000
}
```

Subscribers receive **two consecutive WebSocket messages** per audio chunk:

1. A JSON header:

```json
{
  "type": "audio_frame_header",
  "clientId": "...",
  "participantId": "...",
  "name": "Alice",
  "sampleRate": 48000,
  "channels": 1,
  "samples": 4096,
  "ts": 1700000000000,
  "encoding": "pcm_s16le",
  "byteLength": 8192
}
```

2. A raw binary WebSocket frame containing the PCM16-LE audio data (`byteLength` bytes).

See `subscriber_example.py` for a minimal reference consumer.

### Lifecycle events

| `type`                    | Direction              | Description                        |
|---------------------------|------------------------|------------------------------------|
| `bridge_connection_opened`| server → subscribers   | An ingest or subscriber connected  |
| `bridge_connection_closed`| server → subscribers   | A client disconnected              |
| `participant_attached`    | ingest → subscribers   | Audio capture started for a participant |
| `participant_detached`    | ingest → subscribers   | Audio capture stopped for a participant |
| `capture_started`         | ingest → subscribers   | Capture session started            |
| `capture_stopped`         | ingest → subscribers   | Capture session stopped            |
