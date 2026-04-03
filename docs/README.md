# Foundry Bridge Documentation

Documentation is organized by user need. Find the section that matches what you're trying to do.

## Learn — build familiarity with the system

Start here if you are new to Foundry Bridge.

- [Get started with Foundry Bridge](./getting-started.md) — run the full stack and create your first campaign record end to end

## Accomplish — complete a specific task

Use these guides when you know what you want to do and need to know how.

- [How to set up API keys](./how-to/setup-api-keys.md) — configure Deepgram and LLM provider credentials
- [How to run local development](./how-to/local-development.md) — run the backend and frontend locally with Postgres in Docker
- [How to deploy with Docker Compose](./how-to/deploy-docker-compose.md) — run the full stack with the repository Docker Compose setup
- [How to integrate Foundry VTT userscript](./how-to/foundry-integration.md) — connect live Foundry audio to the bridge
- [How to load demo data](./how-to/load-demo-data.md) — seed the database with example session data
- [How to run the audit workflow](./how-to/audit-workflow.md) — trigger audits and review or apply suggested changes
- [How to run database migrations](./how-to/database-migrations.md) — generate, apply, and roll back Alembic migrations
- [How to troubleshoot common issues](./how-to/troubleshoot-common-issues.md) — diagnose and fix common local and Docker problems
- [How to contribute changes](./how-to/contributing.md) — prepare and submit a contribution

## Look up — find accurate facts and details

Use these when you need to verify a specific value, command, or schema while working.

- [API reference](./reference/api.md) — REST endpoints, parameters, and reason codes
- [Environment variables](./reference/environment-variables.md) — all runtime configuration options
- [CLI commands](./reference/cli-commands.md) — Make targets, Alembic commands, Docker Compose commands
- [Database schema](./reference/database-schema.md) — tables, columns, constraints, and migration lineage
- [WebSocket protocol](./reference/websocket-protocol.md) — message types, field definitions, and validation rules
- [Backend modules](./reference/modules.md) — Python module responsibilities and entrypoints

## Understand — grasp concepts and design decisions

Read these when you want to understand why the system works the way it does.

- [Architecture and design decisions](./architecture.md) — pipeline structure, concurrency model, and trade-offs
