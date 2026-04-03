# How to Set Up API Keys

This guide shows you how to configure the required model and transcription credentials for Foundry Bridge.

## Prerequisites

- Repository cloned locally
- Access to your Deepgram API key
- Access to either OpenAI or Anthropic API key

## Step 1: Create or open `.env`

From the repository root, create `.env` if it does not exist, then add:

```bash
DEEPGRAM_API_KEY=replace-with-your-key
MODEL_PROVIDER=openai
MODEL=gpt-5.4
OPENAI_API_KEY=replace-with-your-key
POSTGRES_PASSWORD=foundry
DATABASE_URL=postgresql://foundry:foundry@postgres:5432/foundry_bridge
```

## Step 2: Configure Anthropic instead of OpenAI (optional branch)

If you use Anthropic, set:

```bash
MODEL_PROVIDER=anthropic
MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=replace-with-your-key
```

When `MODEL_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` is required.

## Step 3: Apply the new configuration

If services are not yet running:

```bash
docker compose up -d --build
```

If services are already running, restart the bridge service to pick up the updated environment:

```bash
docker compose restart bridge
```

## Step 4: Verify configuration is accepted

Check service logs:

```bash
docker compose logs bridge --tail=100
```

Look for normal startup output. A missing or mismatched key will surface as a startup error in these logs.

## Related

- [Environment variables](../reference/environment-variables.md)
- [How to deploy with Docker Compose](./deploy-docker-compose.md)
- [How to run local development](./local-development.md)
