# How to Load Demo Data

This guide shows you how to load the provided session seed SQL files into PostgreSQL.

## Prerequisites

- Docker Compose stack running with `postgres`
- Migrations already applied
- `foundry-postgres` container running

## Step 1: Start the required service

```bash
docker compose up -d postgres
```

## Step 2: Run the seed loader script

From repository root:

```bash
bash seeds/load_01.sh
```

The script executes all `seeds/01*.sql` files in sorted order and pauses between files.

## Step 3: Verify inserted data

```bash
curl http://localhost:8767/api/games
curl http://localhost:8767/api/games/1/notes
curl http://localhost:8767/api/games/1/entities
```

## Related

- [How to run local development](./local-development.md)
- [How to run the audit workflow](./audit-workflow.md)
- [Database schema](../reference/database-schema.md)
