# Understanding foundry-bridge's architecture

foundry-bridge is a small hub-and-span message bus specialised for real-time audio. This document explains the design decisions behind it and how the major components relate to each other.

## Why a separate bridge process?

Foundry VTT runs in the browser with no direct access to system audio pipelines or persistent services. A browser tab can open WebSocket connections, but it cannot act as a server or route audio to multiple consumers. The bridge solves this by giving the browser a single, stable target to push audio to, and then handling all fan-out, buffering, and consumer lifecycle management on the server side.

This separation means the browser-side userscript stays minimal — capture audio, open a WebSocket, push frames — while all the complexity of managing subscribers lives in the Python process.

## The two-role WebSocket model

The bridge distinguishes two kinds of WebSocket client:

- **Ingest clients** are audio sources. In practice this is always the userscript running in a Foundry VTT tab. An ingest client sends audio frames and lifecycle events. The bridge does not send audio back to ingest clients.
- **Subscriber clients** are audio consumers. They receive every frame and event broadcast by the bridge. A subscriber never sends audio to the bridge.

This asymmetry is enforced at the handshake step: the client declares its role in the `hello` message, and the server routes accordingly. The result is a clean hub-and-spoke topology where ingest clients and subscriber clients never communicate directly — the bridge mediates everything.

A key consequence of this design: adding a new subscriber has zero impact on ingest clients. The userscript is unaware of how many subscribers exist or what they do.

## The two-message audio frame

Each audio chunk is transmitted as two consecutive WebSocket messages: a JSON header followed by a binary frame. The JSON header carries all metadata (participant identity, sample rate, channel count, timestamp, byte length). The binary frame carries the raw PCM16-LE samples.

This design avoids the overhead and complexity of mixing metadata into a binary envelope. JSON is easy to parse and log. Binary frames are efficient to relay. The server can inspect and re-annotate the header (adding `clientId`, `encoding`, `byteLength`) without touching the audio bytes.

The subscriber receives headers and binary frames sequentially. The `BaseSubscriber` base class manages the state machine that pairs the two messages before calling `on_audio_frame`, so concrete subscribers never see orphaned binary frames under normal operation.

## Why PCM16-LE?

LiveKit (the WebRTC library Foundry VTT uses for voice) decodes audio tracks into raw PCM. The userscript taps this decoded PCM at 48 kHz, 16-bit, mono — the standard format for voice processing. Passing raw PCM through the bridge avoids re-encoding at the source and lets each subscriber choose its own codec independently.

Deepgram's streaming API accepts raw PCM16 directly, which is why the transcriber can deliver audio without any transcoding step.

## The subscriber abstraction

`BaseSubscriber` exists to reduce the boilerplate required to write a new consumer. The connection, handshake, reconnect-on-error handling, and the state machine that pairs audio headers with binary frames are all generalised in the base class. A concrete subscriber only needs to answer two questions: "what should I do with an audio frame?" and "what should I do with a lifecycle event?"

This makes it straightforward to build diverse consumers — transcribers, recorders, real-time monitors, analysis pipelines — without duplicating protocol code.

## How the transcriber integrates

The transcriber subscriber creates one async worker task per participant when a `participant_attached` event arrives. Each worker maintains its own Deepgram streaming session and forwards audio frames from that participant to Deepgram over a persistent WebSocket. When Deepgram signals end-of-turn, the transcript is written to PostgreSQL.

The per-participant worker architecture means Deepgram sees a clean, single-speaker stream for each participant, even when multiple participants are talking simultaneously. Each stream is independent; a dropout or reconnect for one participant does not affect the others.

When a `participant_detached` event arrives, the corresponding worker gracefully closes its Deepgram session and persists any pending transcript.

## Design trade-offs

**Single process, in-memory fan-out** — The bridge holds subscriber sets in memory and broadcasts synchronously in a loop. This is simple and has very low latency, but means a slow or misbehaving subscriber can delay delivery to others. For the target use case (a handful of subscribers on a local or LAN-accessible server), this is acceptable.

**No persistence in the bridge** — The bridge does not buffer or replay audio. If a subscriber disconnects, it misses frames that arrived while it was gone. This keeps the bridge stateless and memory-bounded, at the cost of reliability for slow-starting or reconnecting subscribers.

**No authentication** — The bridge has no credentials check. Anyone who can reach port `8765` can connect as ingest or subscriber. Operate the bridge on a trusted network or behind a firewall.

## Further reading

- [WebSocket protocol reference](../reference/websocket-protocol.md) — message format details
- [BaseSubscriber API reference](../reference/base-subscriber-api.md) — the subscriber abstraction in full
- [How to write a custom subscriber](../how-to/write-a-custom-subscriber.md)
- [Tutorial: Build your first foundry-bridge setup](../tutorials/getting-started.md)
