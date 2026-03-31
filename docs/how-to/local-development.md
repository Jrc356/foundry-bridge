# How to Run Local Development

This guide shows you how to run the backend and frontend locally while using PostgreSQL in Docker.

## Prerequisites

- Python 3.10+
- `uv`
- Node.js + npm
- Docker Compose
- Configured `.env` file

## Step 1: Install dependencies

From the repository root:

```bash
make sync
cd frontend && npm install
cd ..
```

## Step 2: Start PostgreSQL

```bash
docker compose up -d postgres
```

## Step 3: Apply migrations

```bash
uv run alembic upgrade head
```

## Step 4: Run the backend

```bash
make run
```

This starts WebSocket ingestion (`8765`), health (`8766`), and API/SPA hosting (`8767`).

## Step 5: Run the frontend dev server

In another terminal:

```bash
make run-frontend
```

The frontend runs at `http://localhost:5173` and proxies `/api` to `http://localhost:8767`.

## Step 6: Verify local loop

```bash
curl http://localhost:8766/health
curl http://localhost:8767/api/games
```

## Optional branch: run API-only backend

If you only need REST API development:

```bash
make run-api
```

## Related

- [How to set up API keys](./setup-api-keys.md)
- [How to run database migrations](./database-migrations.md)
- [CLI commands](../reference/cli-commands.md)
