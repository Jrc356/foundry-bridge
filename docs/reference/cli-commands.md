# CLI Commands

Command surfaces used in this repository.

## Make Targets

|Target|Command|Description|
|---|---|---|
|`make sync`|`uv sync`|Sync Python dependencies.|
|`make sync-transcriber`|`uv sync --extra transcriber`|Sync Python dependencies with transcriber extras.|
|`make run`|`uv run foundry-bridge`|Run combined server entrypoint (WebSocket, health, API/SPA).|
|`make run-transcriber`|`uv run foundry-bridge-transcriber`|Run standalone transcriber script entrypoint if available in environment.|
|`make run-api`|`uv run uvicorn foundry_bridge.api:app --reload --port 8767`|Run FastAPI app in reload mode.|
|`make run-frontend`|`cd frontend && npm run dev`|Run Vite development server.|
|`make build`|`docker compose build`|Build Docker images.|
|`make up`|`docker compose up`|Start compose stack in foreground.|
|`make up-bridge`|`docker compose up bridge`|Start bridge service only (with dependencies as needed).|
|`make down`|`docker compose down`|Stop compose stack and remove containers.|

## Python Entrypoints

|Command|Description|
|---|---|
|`uv run foundry-bridge`|Main application process from project scripts.|

## Alembic Commands

|Command|Description|
|---|---|
|`uv run alembic upgrade head`|Apply all pending migrations.|
|`uv run alembic downgrade -1`|Revert one migration step.|
|`uv run alembic revision --autogenerate -m "message"`|Generate migration from ORM diff.|
|`uv run alembic current`|Show current migration revision.|
|`uv run alembic history`|Show migration timeline.|

## Docker Compose Commands

|Command|Description|
|---|---|
|`docker compose up -d`|Start stack in background.|
|`docker compose logs bridge --tail=100`|Tail bridge logs.|
|`docker compose restart bridge`|Restart bridge service.|
|`docker compose exec postgres psql -U foundry -d foundry_bridge`|Open psql shell inside postgres service.|

## See also

- [How to run local development](../how-to/local-development.md)
- [How to run database migrations](../how-to/database-migrations.md)
- [Environment variables](./environment-variables.md)
