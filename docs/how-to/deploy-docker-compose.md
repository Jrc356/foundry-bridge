# How to Deploy with Docker Compose

This guide shows you how to run Foundry Bridge using the repository Docker Compose stack.

## Prerequisites

- Docker Engine and Docker Compose
- Valid API keys for your configured model provider and Deepgram

## Step 1: Create `.env`

Set at least:

```bash
DEEPGRAM_API_KEY=replace-with-your-key
OPENAI_API_KEY=replace-with-your-key
POSTGRES_PASSWORD=foundry
DATABASE_URL=postgresql://foundry:foundry@postgres:5432/foundry_bridge
MODEL_PROVIDER=openai
MODEL=gpt-5.4
```

## Step 2: Build images

```bash
docker compose build
```

## Step 3: Start services

```bash
docker compose up -d
```

This starts:

- `postgres`
- `migrate`
- `bridge`

## Step 4: Verify services

```bash
curl http://localhost:8766/health
curl http://localhost:8767/api/games
```

## Step 5: Review logs

```bash
docker compose logs bridge --tail=100
```

## Step 6: Stop deployment

```bash
docker compose down
```

## Related

- [Environment variables](../reference/environment-variables.md)
- [How to set up API keys](./setup-api-keys.md)
- [How to troubleshoot common issues](./troubleshoot-common-issues.md)
