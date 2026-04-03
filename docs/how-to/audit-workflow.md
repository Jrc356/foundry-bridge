# How to Run the Audit Workflow

This guide shows you how to trigger an audit run, review flags, and apply or dismiss suggested changes.

## Prerequisites

- Running API server on `http://localhost:8767`
- Existing game with generated notes
- A known `game_id`

## Step 1: Trigger an audit run

```bash
curl -X POST "http://localhost:8767/api/games/1/audit-runs/trigger"
```

Optional forced run:

```bash
curl -X POST "http://localhost:8767/api/games/1/audit-runs/trigger?force=true"
```

## Step 2: Inspect audit runs

```bash
curl "http://localhost:8767/api/games/1/audit-runs"
```

## Step 3: List pending flags

```bash
curl "http://localhost:8767/api/games/1/audit-flags?status=pending&limit=50&offset=0"
```

## Step 4: Apply a flag

```bash
curl -X POST "http://localhost:8767/api/games/1/audit-flags/123/apply"
```

## Step 5: Dismiss or reopen a flag

Dismiss:

```bash
curl -X POST "http://localhost:8767/api/games/1/audit-flags/123/dismiss"
```

Reopen:

```bash
curl -X POST "http://localhost:8767/api/games/1/audit-flags/123/reopen"
```

## Related

- [API reference](../reference/api.md)
- [Database schema](../reference/database-schema.md)
- [How to load demo data](./load-demo-data.md)
- [Architecture and design decisions](../architecture.md) — explains what audit flags are and why audits are a separate pipeline
