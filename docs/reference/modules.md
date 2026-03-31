# Backend Modules

Python modules under `src/foundry_bridge`.

## Runtime entrypoints

|Module|Responsibility|
|---|---|
|`server.py`|Main runtime entrypoint; hosts WebSocket ingestion, health server, and FastAPI server; starts background tasks.|
|`api.py`|REST API schemas and route handlers; optional static frontend serving when build output exists.|

## Pipeline modules

|Module|Responsibility|
|---|---|
|`transcriber.py`|Deepgram realtime streaming workers and transcript persistence hooks.|
|`note_taker.py`|Polling loop for unprocessed transcripts and note generation orchestration.|
|`note_generator.py`|LLM agent and structured note output model; model-provider config validation.|
|`auditor.py`|Audit scheduler and run orchestration with game-lock coordination.|
|`audit_generator.py`|LLM audit generation for mutation suggestions and confidence classification.|

## Data and state modules

|Module|Responsibility|
|---|---|
|`db.py`|Async engine/session setup, persistence helpers, search functions, embedding helpers.|
|`models.py`|SQLAlchemy ORM models, enum values, and join-table declarations.|
|`locks.py`|Shared in-memory per-game asyncio lock map.|

## Logging and packaging

|Module|Responsibility|
|---|---|
|`__init__.py`|Logging formatter setup and log-level/color configuration from env vars.|

## See also

- [Architecture and design decisions](../architecture.md)
- [Database schema](./database-schema.md)
- [API reference](./api.md)
