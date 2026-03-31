# How to Run Database Migrations

This guide shows you how to create, apply, and roll back Alembic migrations in Foundry Bridge.

## Prerequisites

- Python dependencies installed (`make sync`)
- PostgreSQL reachable through `DATABASE_URL`
- Existing `.env` in repository root

## Step 1: Generate a migration after model changes

```bash
uv run alembic revision --autogenerate -m "describe change"
```

This creates a new file in `alembic/versions/`.

## Step 2: Review generated migration

Open the generated file and confirm:

- Table and column names are expected
- Constraints and indexes are present
- No destructive operation is included accidentally

## Step 3: Apply migrations

```bash
uv run alembic upgrade head
```

## Step 4: Verify revision state

```bash
uv run alembic current
uv run alembic history
```

## Step 5: Roll back one step (if needed)

```bash
uv run alembic downgrade -1
```

## Related

- [Database schema](../reference/database-schema.md)
- [How to run local development](./local-development.md)
- [How to load demo data](./load-demo-data.md)
