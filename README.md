# Foundry Bridge

Foundry Bridge captures live tabletop session audio, transcribes it, extracts structured campaign data, and exposes that data through a searchable web UI and API.

## Quick Start

Use the tutorial for the fastest path to a working stack:

- [Get Started with Foundry Bridge](docs/getting-started.md)

## Documentation

Documentation is organized by user need (Diataxis):

- Learn: [docs/getting-started.md](docs/getting-started.md)
- Accomplish: [docs/how-to](docs/how-to)
- Look up: [docs/reference](docs/reference)
- Understand: [docs/architecture.md](docs/architecture.md)

Central docs index:

- [docs/README.md](docs/README.md)

## Local Commands

|Task|Command|
|---|---|
|Sync Python dependencies|`make sync`|
|Run backend (WS + HTTP + API)|`make run`|
|Run API only|`make run-api`|
|Run frontend dev server|`make run-frontend`|
|Build Docker images|`make build`|
|Start Docker stack|`make up`|
|Stop Docker stack|`make down`|

## Service Endpoints

|Service|URL|
|---|---|
|Frontend|`http://localhost:5173`|
|API|`http://localhost:8767`|
|Swagger|`http://localhost:8767/docs`|
|ReDoc|`http://localhost:8767/redoc`|
|Health|`http://localhost:8766/health`|
|WebSocket ingest|`ws://localhost:8765`|

## Repository Layout

|Path|Purpose|
|---|---|
|`src/foundry_bridge`|Backend runtime, API, pipelines, schema|
|`frontend`|React + TypeScript UI|
|`alembic`|DB migrations|
|`seeds`|Demo SQL seed scripts|
|`docs`|Diataxis documentation suite|

## Contributing

Use the operational guides in [docs/how-to](docs/how-to) for local development, migrations, and troubleshooting before opening a pull request.
