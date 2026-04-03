# Get Started with Foundry Bridge

In this tutorial, we will run Foundry Bridge with Docker Compose, create your first campaign record, and confirm the UI and API are working end to end. By the end, we will have a live stack with a working database, a populated game entry, and a browsable frontend.

## Prerequisites

- Docker Engine with Docker Compose
- A Deepgram API key
- An OpenAI API key

## Step 1: Create a local environment file

From the repository root, create a `.env` file with the required values:

```bash
cat > .env <<'EOF'
DEEPGRAM_API_KEY=replace-with-your-key
OPENAI_API_KEY=replace-with-your-key
POSTGRES_PASSWORD=foundry
DATABASE_URL=postgresql://foundry:foundry@postgres:5432/foundry_bridge
MODEL_PROVIDER=openai
MODEL=gpt-5.4
LOG_LEVEL=INFO
EOF
```

You should see a new `.env` file in the repository root. This file is already excluded from version control.

## Step 2: Start the stack

Run:

```bash
docker compose up
```

Docker will pull or build images, start the database, run migrations, and bring up the bridge service. After a moment, you should see log output from all three services:

- `postgres` — database accepting connections
- `migrate` — migrations applied and process exited
- `bridge` — WebSocket, health, and API servers listening

Notice that `migrate` is expected to exit after the migration completes. That is normal behavior, not a failure.

## Step 3: Verify health and API endpoints

In a new terminal, run:

```bash
curl http://localhost:8766/health
curl http://localhost:8767/api/games
```

You should see:

- A health payload: `{"status": "ok"}`
- A JSON list from `/api/games` (empty on first run is expected)

## Step 4: Create your first game

Run:

```bash
curl -X POST http://localhost:8767/api/games \
  -H "Content-Type: application/json" \
  -d '{"hostname":"local.foundry.test","world_id":"demo-world","name":"Demo Campaign"}'
```

You should see a JSON object containing an `id` and the fields you submitted. Remember the `id` — you will use it to address this campaign in all subsequent API calls.

## Step 5: Open the UI and confirm the campaign appears

Open `http://localhost:5173` in your browser.

You should see your campaign in the game list. Click through to the detail page and notice that all the data tabs are present and empty, ready to be filled by live session ingestion.

## What you've built

We now have a running Foundry Bridge stack: database, migration history, API server, and frontend, all communicating correctly. We also created and browsed our first campaign record.

## Next steps

- To connect live Foundry audio to this stack, use [How to integrate Foundry VTT userscript](./how-to/foundry-integration.md)
- To run the backend and frontend in local development mode, use [How to run local development](./how-to/local-development.md)
- To understand why the system is structured the way it is, read [Architecture and design decisions](./architecture.md)
- To browse the full API, visit `http://localhost:8767/docs` or refer to the [API reference](./reference/api.md)
