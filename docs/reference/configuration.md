# Configuration

## Environment variables

| Variable | Required by | Default | Description |
|---|---|---|---|
| `DEEPGRAM_API_KEY` | `transcriber` | — | Deepgram API key for the speech-to-text service. No default; the transcriber will not start without it. |
| `DATABASE_URL` | `transcriber`, `migrate` | — | PostgreSQL connection string. Accepts `postgresql://` or `postgresql+asyncpg://` schemes. Example: `postgresql://user:pass@localhost:5432/foundry` |
| `BRIDGE_URI` | `transcriber`, `example` | `ws://127.0.0.1:8765` | WebSocket URI of the bridge server, used by subscriber processes to connect. |
| `POSTGRES_PASSWORD` | Docker Compose | `foundry` | Password for the `postgres` superuser in the Docker Compose PostgreSQL service. |

## CLI entry points

Installed by `uv sync` (or `pip install -e .`).

| Command | Module | Description |
|---|---|---|
| `foundry-bridge` | `foundry_bridge.server:main` | Start the WebSocket bridge server |
| `foundry-bridge-transcriber` | `foundry_bridge.subscribers.transcriber:main` | Start the Deepgram transcriber subscriber |
| `foundry-bridge-example` | `foundry_bridge.subscribers.example:main` | Start the debug/example subscriber |

## Default ports

| Port | Protocol | Service |
|---|---|---|
| `8765` | WebSocket (`ws://`) | Bridge server — ingest and subscriber connections |
| `8766` | HTTP | Health check endpoint (`GET /health`) |
| `5432` | TCP | PostgreSQL (Docker Compose service) |

## Makefile targets

| Target | Description |
|---|---|
| `make sync` | Install base dependencies using `uv sync` |
| `make sync-transcriber` | Install dependencies including `deepgram-sdk` (`uv sync --extra transcriber`) |
| `make run` | Start the bridge server (`uv run foundry-bridge`) |
| `make run-transcriber` | Start the Deepgram transcriber subscriber |
| `make build` | Build all Docker images |
| `make up` | Start all services via Docker Compose |
| `make up-bridge` | Start the bridge service only via Docker Compose |
| `make down` | Stop and remove all Docker Compose containers |

## Docker Compose services

| Service | Image stage | Depends on | Description |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | — | PostgreSQL database with persistent volume and health check |
| `migrate` | `migrate` | `postgres` (healthy) | Runs `alembic upgrade head` once, then exits |
| `bridge` | `bridge` | — | WebSocket bridge server; exposes ports `8765` and `8766` |
| `transcriber` | `transcriber` | `bridge`, `migrate` | Deepgram transcriber subscriber |

## See also

- [How to deploy with Docker Compose](../how-to/deploy-with-docker.md)
- [How to set up live transcription with Deepgram](../how-to/set-up-transcription.md)
