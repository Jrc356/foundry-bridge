# How to Contribute Changes

This guide shows you how to prepare and submit a contribution to Foundry Bridge.

## Prerequisites

- Local development environment working
- Ability to run backend and frontend locally

## Step 1: Create a branch

```bash
git checkout -b your-change-name
```

## Step 2: Implement and verify locally

Use project commands as needed:

```bash
make sync
make run
make run-frontend
```

Apply and verify migrations when schema changes are included.

## Step 3: Validate behavior in UI and API

Check endpoints and UI tabs affected by your change.

## Step 4: Prepare a focused commit

Include only relevant files for the change set.

## Step 5: Open a pull request

Include:

- What changed
- Why it changed
- How it was validated
- Any migration or deployment impact

## Related

- [How to run local development](./local-development.md)
- [How to run database migrations](./database-migrations.md)
- [Architecture and design decisions](../architecture.md)
