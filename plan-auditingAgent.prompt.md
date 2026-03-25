# Auditing Agent Specification

## 1) Purpose

The auditing agent is a background reconciliation service that reads a wider transcript window than the note taker and corrects derived game data.

It is responsible for keeping structured campaign state consistent with transcript evidence by:

- creating missing records,
- updating incorrect records,
- merging/removing invalid records,
- and flagging ambiguous cases for human review.

The auditing agent is authoritative for derived data and may perform create/read/update/delete operations on all derived entities, with one hard exception:

- `Transcript` rows are immutable input data and are never modified or deleted by the auditing system.

## 2) Scope and non-goals

### In scope

- Background audit runs over notes/transcripts since the last completed audit.
- High-confidence auto-corrections.
- Low-confidence flag creation for human apply/dismiss.
- Manual audit trigger endpoint.
- Full audit review/apply UX in frontend.
- Soft-delete workflows for `Quest` and `Thread`.

### Out of scope

- Modifying transcript content.
- First-pass automated test suite (manual verification only for v1).

## 3) Architecture summary

### New backend modules

- `src/foundry_bridge/audit_generator.py`
  - LangGraph ReAct agent modeled after `note_generator.py`.
  - Produces structured `AuditOutput`.
- `src/foundry_bridge/auditor.py`
  - Background runtime that selects note window, invokes generator, writes pipeline results, updates heartbeats, and handles retries/failures.
- `src/foundry_bridge/locks.py`
  - Shared per-game lock registry used by both note and audit pipelines.

### Existing modules updated

- `src/foundry_bridge/models.py`
- `src/foundry_bridge/db.py`
- `src/foundry_bridge/note_taker.py`
- `src/foundry_bridge/server.py`
- `src/foundry_bridge/api.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/pages/GameDetail.tsx`
- `frontend/src/pages/tabs/NotesTab.tsx`
- `frontend/src/pages/tabs/AuditTab.tsx` (new)
- `frontend/src/components/Toast.tsx` (new)

## 4) Data model and migration

### 4.1 New ORM models

#### `AuditRun`

- `id` (PK)
- `game_id` (FK -> games)
- `triggered_at` (timestamp, default now)
- `heartbeat_at` (timestamp, nullable)
- `completed_at` (timestamp, nullable)
- `status` (`running | completed | failed`)
- `trigger_source` (`auto | manual`)
- `notes_audited` (`ARRAY(Integer)`)
- `notes_audited_count` (integer)
- `min_note_id` (integer, nullable)
- `max_note_id` (integer, nullable)
- `audit_note_id` (FK -> notes.id, nullable)

DB guards:

- partial unique index `uq_audit_runs_game_one_running` on `(game_id)` where `status='running'`
- check constraint for valid `status`
- check constraint for valid `trigger_source`

#### `AuditFlag`

- `id` (PK)
- `game_id` (FK -> games)
- `audit_run_id` (FK -> audit_runs)
- `flag_type`
  - `entity_duplicate | missing_entity | missing_event | missing_decision | missing_loot | loot_correction | decision_correction | deletion_candidate | other`
- `target_type` (`entity | quest | thread | loot | decision | note`, nullable)
- `target_id` (integer, nullable)
- `description` (text)
- `suggested_change` (JSONB)
- `status` (`pending | applied | dismissed`)
- `created_at` (timestamp, default now)
- `resolved_at` (timestamp, nullable)

DB guards:

- check constraint for valid `status`

### 4.2 Existing model changes

- `Note`
  - add `is_audit BOOLEAN NOT NULL DEFAULT FALSE`
- `Quest`
  - add `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
  - add `deleted_at TIMESTAMP NULL`
  - add `deleted_reason TEXT NULL`
- `Thread`
  - add `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
  - add `deleted_at TIMESTAMP NULL`
  - add `deleted_reason TEXT NULL`

### 4.3 Migration

Create `alembic/versions/0010_add_audit_tables.py`:

- create `audit_runs`
- create `audit_flags`
- add `notes.is_audit`
- add soft-delete columns to `quests` and `threads`
- add indexes:
  - `audit_runs(game_id)`
  - `audit_runs(status)`
  - `audit_flags(game_id, status)`
  - `audit_flags(audit_run_id)`
- add partial unique index:
  - `CREATE UNIQUE INDEX uq_audit_runs_game_one_running ON audit_runs(game_id) WHERE status='running'`

## 5) Audit generator contract (`audit_generator.py`)

### 5.1 Runtime and config

- uses same model/config env vars as note generator:
  - `MODEL_PROVIDER`
  - `MODEL`
- imports and calls `validate_config()` from `note_generator.py`
- uses the same ReAct graph pattern (`create_agent` + tool calls + structured output)

### 5.2 Function

```python
async def generate_audit(
    game_id: int,
    transcripts: list[Transcript],
    player_characters: list[PlayerCharacter],
) -> AuditOutput
```

Transcript line format is identical to note generation: `[ID:N][SPEAKER]: text` in `turn_index` order.

### 5.3 `AuditOutput`

High-confidence (auto-apply):

- `entity_description_updates`
- `quest_description_updates`
- `quest_status_updates`
- `thread_resolutions`
- `new_entities`
- `new_events`
- `new_decisions`
- `new_loot`
- `new_quests`
- `new_threads`
- `new_quotes`
- `new_combat`
- `thread_text_updates`
- `event_text_updates`
- `decision_corrections`
- `loot_corrections`
- `quote_corrections`

Low-confidence (human review):

- `audit_flags`

Confidence policy:

- only output auto-apply entries when transcript evidence is unambiguous
- route ambiguity/inference to `audit_flags`
- when uncertain: flag, do not auto-apply

### 5.4 Tooling

The agent binds all 9 search tools from note generation plus 3 listing tools.

Inherited tools:

1. `search_quests`
2. `search_entities`
3. `search_open_threads`
4. `search_resolved_threads`
5. `search_events`
6. `search_past_notes`
7. `search_decisions`
8. `search_loot`
9. `search_combat`

New listing tools (bound by `game_id`):

10. `get_all_entities`
11. `get_all_quests`
12. `get_all_open_threads`

Mandatory tool-use rules:

- lookup before create (avoid duplicates)
- verify existence before update/delete/correction output
- resolve `new_threads[].quest_id` via `search_quests` (never guess IDs)
- verify loot corrections with `search_loot`
- verify decision corrections with `search_decisions`
- verify quote corrections with transcript/note search context

Search/listing tools exclude soft-deleted quests/threads by default.

### 5.5 Context preamble

Before model invocation, include compact context in user-facing prompt:

- entity count by type + entity names
- quest names + statuses
- open thread count + texts (truncated)
- player character names

This preamble is orientation only. It does not replace tool calls.

### 5.6 Failure behavior

- `GraphRecursionError` may be raised by LangGraph for recursion/context failure
- caller (`auditor.py`) handles this by failing the run

## 6) DB functions (`db.py`)

### 6.1 Reads

- `get_last_audit_run_for_game(game_id)`
  - returns last run with `status='completed'` only
- `get_notes_since_last_audit(game_id, since_note_id)`
- `get_transcripts_for_notes(note_ids)`
- `get_unaudited_note_count(game_id)`
- `get_all_entities_for_game(game_id)`
- `get_all_quests_for_game(game_id)`
- `get_all_open_threads_for_game(game_id)`

### 6.2 Writes and maintenance

- `create_audit_run(game_id, trigger_source)` -> pre-create running row
- `touch_audit_run_heartbeat(audit_run_id)`
- `fail_audit_run(audit_run_id)`
- `reset_stale_audit_runs(stale_after_minutes=15)`
- `restore_deleted_quest(game_id, quest_id)`
- `restore_deleted_thread(game_id, thread_id)`
- `apply_audit_flag(flag_id)`
- `dismiss_audit_flag(flag_id)`
- `reopen_audit_flag(flag_id)`

### 6.3 Pipeline write contract

`write_audit_pipeline_result(game_id, audit_run_id, output, notes) -> AuditPipelineResult`

Write flow:

1. Step 1 (own transaction): create synthetic audit note
2. Step 2+: single atomic transaction for all correction/create/flag/finalize writes
3. on Step 2+ failure:
   - rollback full transaction
   - call `fail_audit_run`
   - delete synthetic note created in Step 1 (best effort)

Atomicity guarantee:

- all Phase A/B/C writes commit together or not at all
- failed audits do not advance note window

### 6.4 Phases inside atomic transaction

Phase A (corrections):

- apply updates to entities/quests/threads/events/decisions/loot/quotes
- archive quest description history with `note_id=audit_note_id`
- set thread resolution metadata using `audit_note_id`
- handle uniqueness collisions for event/loot corrections by skipping update with warning

Phase B (new data):

- create/upsert new entities/events/decisions/loot/quests/threads/quotes/combat
- enforce ordering: new quests before new threads
- `session.flush()` after new quests so `quest_id` is visible
- link created rows to synthetic audit note via existing note-link tables/FKs

Phase C (flags + finalize):

- insert `audit_flags`
- complete `audit_runs` row (`status=completed`, timestamps, note window fields)

### 6.5 Embeddings

`_write_audit_embeddings(result: AuditPipelineResult)` runs post-commit only.

Rows with embedding columns to process:

- entities
- events
- threads
- decisions
- loot
- notes (synthetic audit note)
- quests
- combat

Excluded:

- `ImportantQuote` (no embedding column currently)

Retry policy on post-commit embedding failure:

- bounded exponential backoff: `5s`, `15s`, `45s`
- max 3 attempts
- then log and stop (do not roll back committed data)

## 7) Audit flag semantics

### 7.1 Status lifecycle

- `pending` -> `applied`
- `pending` -> `dismissed`
- `applied|dismissed` -> `pending` (reopen)

All transitions are idempotent. No-op transitions return success with `noop=true` metadata.

### 7.2 `suggested_change` shapes

- `entity_duplicate`
  - `{"canonical_id": int, "duplicate_id": int}`
- `missing_entity`
  - `{"name": str, "entity_type": str, "description": str}`
- `missing_event`
  - `{"text": str}`
- `missing_decision`
  - `{"decision": str, "made_by": str}`
- `missing_loot`
  - `{"item_name": str, "acquired_by": str}`
- `loot_correction`
  - `{"loot_id": int, "new_item_name": str, "new_acquired_by": str}`
- `decision_correction`
  - `{"decision_id": int, "new_decision": str, "new_made_by": str}`
- `deletion_candidate`
  - `{"table": str, "record_id": int, "reason": str}`
- `other`
  - `{"description": str, "proposed_action": str}`

### 7.3 Apply behavior highlights

- `entity_duplicate`: full atomic merge (re-point FKs and joins, delete duplicate)
- `missing_entity`: insert/upsert and link to audit synthetic note
- `deletion_candidate`:
  - `quests|threads`: soft-delete with reason/timestamp
  - `entities`: FK cleanup + hard delete
  - `events|loot|decisions|important_quotes`: hard delete

## 8) Auditor runtime (`auditor.py`)

### 8.1 Trigger threshold

```python
AUDIT_AFTER_N_NOTES = int(os.environ.get("AUDIT_AFTER_N_NOTES", "5"))
```

Auto-trigger occurs after successful note pipeline completion when unaudited note count meets threshold.

### 8.2 Startup and sweeper

- on service startup, fail stale `running` audits (`>15 minutes` without heartbeat)
- run periodic stale-run sweeper every 5 minutes
- apply startup jitter `0-30s`
- skip games with in-process lock currently held

### 8.3 Shared lock model

`locks.py` exports:

- `_game_locks: dict[int, asyncio.Lock]`
- `get_game_lock(game_id)`

Both note and audit pipelines use the same lock source to avoid overlap.

### 8.4 Core pipeline

`_run_audit_pipeline(game_id, audit_run_id, force=False)`:

1. acquire per-game lock or skip
2. call `embed_unembedded_rows(game_id)`
3. calculate note window from last completed audit
4. collect transcripts from note window
5. load player characters
6. call `generate_audit(...)`
7. call `write_audit_pipeline_result(...)`
8. call `_write_audit_embeddings(...)`

Failure handling:

- `GraphRecursionError`: mark run failed
- early failure before synthetic note creation: delete pre-created run and log structured error
- failures from write phase onward: handled by DB write path (`fail_audit_run` + rollback)

Operational notes:

- create named background tasks
- attach done-callback exception logging
- update heartbeat by phase and with fallback 60s tick during long model/tool operations

## 9) API contract (`api.py`)

### 9.1 Updated schemas

- add `is_audit: bool` to `NoteOut`
- new:
  - `AuditRunOut`
  - `AuditFlagOut`
  - `AuditFlagMutationOut`
  - `AuditRunTriggerOut`

`AuditRunOut` includes `trigger_source` and `audit_note_id`.

### 9.2 Reason-code contract

Wrapper responses include machine-readable `reason_code`.

Baseline reason codes:

- `conflict_running`
- `noop_no_new_notes`
- `schedule_failed`
- `precreate_failed`
- `early_pipeline_failure`

For relevant conflict/error responses, mirror reason code in `X-Reason-Code` header while preserving normal HTTP body detail text.

### 9.3 New endpoints

- `GET /api/games/{game_id}/audit-runs`
  - returns runs newest first
- `POST /api/games/{game_id}/audit-runs/trigger`
  - creates `running` row immediately, then schedules background run
  - supports `force=true`
  - returns `200 noop=true run=null` when `force=false` and no unaudited notes
  - returns `409` when run already active (query check + lock check + unique-index race guard)
- `GET /api/games/{game_id}/audit-flags?status=&offset=&limit=`
- `POST /api/games/{game_id}/audit-flags/{flag_id}/apply`
- `POST /api/games/{game_id}/audit-flags/{flag_id}/dismiss`
- `POST /api/games/{game_id}/audit-flags/{flag_id}/reopen`
- `POST /api/games/{game_id}/quests/{quest_id}/restore`
- `POST /api/games/{game_id}/threads/{thread_id}/restore`
- `GET /api/entities/{entity_id}`

### 9.4 Modified endpoint behavior

- `DELETE /api/notes/{id}` returns `409` when target note has `is_audit=True`

## 10) Frontend contract and UX

### 10.1 Types (`frontend/src/types.ts`)

Add:

- `FlagType`
- `FlagStatus`
- `ReasonCode`
- `AuditRun`
- `AuditFlag`
- `AuditFlagMutation`
- `AuditRunTrigger`

Update existing `Note` type:

- add `is_audit: boolean`

### 10.2 API client (`frontend/src/api.ts`)

Add:

- `getAuditRuns(gameId)`
- `triggerAudit(gameId, force?)`
- `getAuditFlags(gameId, status?, offset?, limit?)`
- `applyAuditFlag(gameId, flagId)`
- `dismissAuditFlag(gameId, flagId)`
- `reopenAuditFlag(gameId, flagId)`
- `getEntity(entityId)`

### 10.3 Game detail integration (`GameDetail.tsx`)

- add `Audit` tab and route
- fetch pending flags at page level for nav badge
- badge display capped to `50+`

### 10.4 Audit tab (`AuditTab.tsx`)

Contains:

- run header with latest run status + trigger button
- status filters (`All`, `Pending`, `Applied`, `Dismissed`)
- paginated flag list (`offset`, `limit=50`, load more)
- flag cards with apply/dismiss actions

Behavior:

- polling `audit-runs` only while latest run is `running`
- invalidate domain queries when latest run transitions `running -> completed`
- optimistic apply/dismiss UI with 5-second undo toast
- use server `message` when present in mutation response

### 10.5 Notes tab behavior (`NotesTab.tsx`)

For `note.is_audit === true`:

- show `Audit Correction` badge
- render muted summary style
- hide delete button
- expanded view uses audit-specific heading:
  - `Corrected by Foundry Bridge Auditor`

Audit notes remain visible in regular notes API/list; frontend differentiates via `is_audit`.

## 11) Trigger semantics and concurrency

- auto trigger path:
  - threshold check in caller logic
  - pre-create run row with `trigger_source='auto'`
  - schedule background task
- manual trigger path:
  - pre-create run row with `trigger_source='manual'`
  - supports `force=true`

Run conflict prevention is layered:

1. query for existing `running` row
2. in-process game lock check
3. DB partial unique index race protection

Scheduling policy is best-effort sequential with compensating cleanup:

- if scheduling fails after precreate, delete pre-created run and return `schedule_failed`

## 12) Security and integrity constraints

- transcripts are immutable and excluded from audit writes/deletes
- all destructive actions are constrained to derived entities only
- high-confidence auto-apply is evidence-gated; ambiguous actions require human flag review
- all multi-entity apply operations that can violate referential integrity run in transactions

## 13) Verification (manual for v1)

- run migration: `alembic upgrade head`
- load seed chain: `01`, `01b`, `01c`, `01d`, `01e`
- execute enough note runs to cross `AUDIT_AFTER_N_NOTES`
- verify `audit_runs` row lifecycle and completion
- verify `audit_flags` population
- verify apply/dismiss/reopen endpoint behavior and idempotency
- verify corrected rows are reflected in domain tabs
- verify quest description history archived on audit updates
- verify per-game lock blocks concurrent note/audit overlap
- verify `DELETE /notes/{id}` blocks audit notes with `409`

## 14) Canonical implementation files

- `alembic/versions/0010_add_audit_tables.py` (new)
- `src/foundry_bridge/models.py`
- `src/foundry_bridge/db.py`
- `src/foundry_bridge/locks.py` (new)
- `src/foundry_bridge/audit_generator.py` (new)
- `src/foundry_bridge/auditor.py` (new)
- `src/foundry_bridge/note_taker.py`
- `src/foundry_bridge/server.py`
- `src/foundry_bridge/api.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/pages/GameDetail.tsx`
- `frontend/src/pages/tabs/AuditTab.tsx` (new)
- `frontend/src/pages/tabs/NotesTab.tsx`
- `frontend/src/components/Toast.tsx` (new)

This document is the canonical source for the auditing agent implementation.
