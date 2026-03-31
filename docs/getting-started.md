# Get Started with Foundry Bridge

In this tutorial, we will run Foundry Bridge with Docker Compose, create your first campaign record, and confirm the UI and API are working end to end.

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

You should see a new `.env` file in the repository root.

## Step 2: Start the stack

Run:

```bash
docker compose up
```

After startup, you should see all three services running:

- `postgres`
- `migrate`
- `bridge`

## Step 3: Verify health and API endpoints

In a new terminal, run:

```bash
curl http://localhost:8766/health
curl http://localhost:8767/api/games
```

You should see:

- A health payload with `{"status": "ok"}`
- A JSON list from `/api/games` (often empty on first run)

## Step 4: Create your first game

Run:

```bash
curl -X POST http://localhost:8767/api/games \
  -H "Content-Type: application/json" \
  -d '{"hostname":"local.foundry.test","world_id":"demo-world","name":"Demo Campaign"}'
```

You should see a JSON object containing an `id` and your campaign fields.

## Step 5: Open the UI and confirm the campaign appears

Open `http://localhost:5173` in your browser.

You should see your campaign in the game list, and you should be able to open the detail page and tabs.

## What you've built

You now have a running Foundry Bridge stack with a working database, migration flow, API server, and frontend. You also created and viewed your first campaign record.

## Next steps

- To connect live Foundry audio, use [How to integrate Foundry VTT userscript](./how-to/foundry-integration.md)
- To run the app in split local mode, use [How to run local development](./how-to/local-development.md)
- To understand the runtime architecture, read [Architecture and design decisions](./architecture.md)
- To browse API details, use [API reference](./reference/api.md)
