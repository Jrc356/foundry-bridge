# foundry-bridge

A WebSocket bridge that captures per-participant audio from [Foundry VTT](https://foundryvtt.com/)'s LiveKit voice chat and streams it to any number of subscriber clients — for transcription, recording, or any custom audio processing pipeline.

```
Foundry VTT (browser)
   └── userscript.js  ──[WebSocket / PCM16]──▶  foundry_bridge.server  ──▶  subscriber clients
         (ingest)                                                            (e.g. transcribers)
```

## Documentation

| | |
|---|---|
| **[Tutorial: Build your first foundry-bridge setup](docs/tutorials/getting-started.md)** | New here? A hands-on walkthrough from install to working audio capture. |
| **[How-to guides](docs/how-to/)** | Task-oriented guides for operators and subscriber developers. |
| **[Reference](docs/reference/)** | Complete specs for the WebSocket protocol, API, configuration, and database schema. |
| **[Explanation: Architecture](docs/explanation/architecture.md)** | Design decisions and architectural concepts behind foundry-bridge. |

### How-to guides

- [How to install the userscript](docs/how-to/install-the-userscript.md) — Set up audio capture in your Foundry VTT browser tab
- [How to deploy with Docker Compose](docs/how-to/deploy-with-docker.md) — Run the full stack in containers
- [How to set up live transcription with Deepgram](docs/how-to/set-up-transcription.md) — Connect speech-to-text and persist transcripts to PostgreSQL
- [How to write a custom subscriber](docs/how-to/write-a-custom-subscriber.md) — Build your own audio consumer

### Reference

- [WebSocket protocol](docs/reference/websocket-protocol.md) — Handshake, audio frames, lifecycle events
- [BaseSubscriber API](docs/reference/base-subscriber-api.md) — Abstract class, methods, and type signatures
- [Configuration](docs/reference/configuration.md) — Environment variables, CLI entry points, Makefile targets, ports
- [Database schema](docs/reference/database-schema.md) — The `transcripts` table
