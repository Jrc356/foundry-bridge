# How to deploy with Docker Compose

This guide shows you how to run the full foundry-bridge stack — bridge server, PostgreSQL database, Alembic migrations, and the Deepgram transcriber — using Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) installed
- A [Deepgram](https://deepgram.com/) API key (required only if running the transcriber service)

## Deploying the bridge server only

To run just the bridge server without the transcriber or database:

```bash
docker compose up bridge
```

The bridge server will be available at `ws://localhost:8765`. The health check endpoint is at `http://localhost:8766/health`.

To run in the background:

```bash
docker compose up -d bridge
```

## Deploying the full stack

The full stack includes PostgreSQL, Alembic migrations, and the Deepgram transcriber in addition to the bridge.

### Step 1: Set your Deepgram API key

Export the key in your shell, or create a `.env` file in the project root:

```bash
# Shell export
export DEEPGRAM_API_KEY=your_key_here

# Or in .env
DEEPGRAM_API_KEY=your_key_here
```

### Step 2: Build all images

```bash
docker compose build
```

### Step 3: Start all services

```bash
docker compose up
```

Docker Compose starts all services in dependency order:

1. **postgres** — waits until healthy
2. **migrate** — runs `alembic upgrade head`, then exits
3. **bridge** — starts the WebSocket server
4. **transcriber** — connects to the bridge and streams audio to Deepgram

All services must be healthy before the transcriber starts. If `migrate` fails, the transcriber will not start.

To run in the background:

```bash
docker compose up -d
```

### Step 4: Verify the stack

Check the bridge health endpoint:

```bash
curl http://localhost:8766/health
```

Expected response:

```json
{"status": "ok"}
```

Check service logs:

```bash
docker compose logs bridge
docker compose logs transcriber
```

## Stopping the stack

```bash
docker compose down
```

To also remove the PostgreSQL data volume:

```bash
docker compose down -v
```

## Environment variables

Refer to the [configuration reference](../reference/configuration.md) for the full list of environment variables accepted by each service.

## Related

- [How to set up live transcription with Deepgram](./set-up-transcription.md) — configure the transcriber
- [Configuration reference](../reference/configuration.md) — all environment variables and defaults
