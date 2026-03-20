# How to set up live transcription with Deepgram

This guide shows you how to configure the foundry-bridge transcriber subscriber to transcribe Foundry VTT voice audio in real time using Deepgram and persist the results to a PostgreSQL database.

## Prerequisites

- foundry-bridge installed (`uv sync`)
- A [Deepgram](https://deepgram.com/) account with an API key
- A running PostgreSQL instance (local or remote)
- The bridge server running (`uv run foundry-bridge` or via Docker Compose)

## Step 1: Install the transcriber dependencies

The Deepgram SDK is an optional dependency, installed via the `transcriber` extra:

```bash
uv sync --extra transcriber
```

## Step 2: Set the required environment variables

The transcriber requires two environment variables:

```bash
export DEEPGRAM_API_KEY=your_deepgram_api_key
export DATABASE_URL=postgresql://user:password@localhost:5432/foundry
```

`DATABASE_URL` must use the `postgresql://` scheme. The transcriber will automatically convert it to `postgresql+asyncpg://` for the async driver.

## Step 3: Run the database migrations

Before starting the transcriber, create the `transcripts` table:

```bash
uv run alembic upgrade head
```

## Step 4: Start the transcriber

```bash
uv run foundry-bridge-transcriber
```

The transcriber connects to the bridge at `ws://127.0.0.1:8765` by default. If your bridge is on a different host or port, set `BRIDGE_URI`:

```bash
BRIDGE_URI=ws://192.168.1.5:8765 uv run foundry-bridge-transcriber
```

## Step 5: Verify transcripts are being stored

While audio is being captured in Foundry VTT, connect to the database and query the `transcripts` table:

```sql
SELECT participant_id, character_name, turn_index, transcript, created_at
FROM transcripts
ORDER BY created_at DESC
LIMIT 10;
```

New rows will appear after each participant's turn ends (Deepgram emits an `EndOfTurn` event when it detects a pause in speech).

## Running with Docker Compose

If you prefer to run everything in containers, set `DEEPGRAM_API_KEY` and use:

```bash
docker compose up
```

Refer to [How to deploy with Docker Compose](./deploy-with-docker.md) for details.

## Related

- [Database schema reference](../reference/database-schema.md) — `transcripts` table columns and types
- [Configuration reference](../reference/configuration.md) — all environment variables
- [Explanation: architecture](../explanation/architecture.md) — how the transcriber integrates with the bridge
