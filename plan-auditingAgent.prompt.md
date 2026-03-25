# Auditing Agent — Implementation Plan

## Overview

An `auditor.py` background agent (modeled after `note_taker.py`) that analyzes all transcripts since the last audit against the current game state, driven by a new LangGraph agent in `audit_generator.py`. It auto-applies high-confidence corrections and creates `AuditFlag` records for low-confidence findings a human can review and apply or dismiss. Triggered automatically after every N note runs per game.

---

## Phase 1 — Database Schema

### New ORM models in `src/foundry_bridge/models.py`

**`AuditRun`**
- `id` — PK
- `game_id` — FK → games
- `triggered_at` — timestamp (default now)
- `heartbeat_at` — timestamp (nullable): periodically updated while the run is active
- `completed_at` — timestamp (nullable)
- `status` — VARCHAR: `running` | `completed` | `failed`
- `trigger_source` — VARCHAR: `auto` | `manual`
- `notes_audited` — ARRAY(Integer): note IDs included in this audit window
- `notes_audited_count` — Integer: compact count summary
- `min_note_id` — Integer (nullable): minimum audited note ID for this run
- `max_note_id` — Integer (nullable): maximum audited note ID for this run
- `audit_note_id` — FK → notes.id (nullable): synthetic note created during this audit run
- DB-level guard: partial unique index `uq_audit_runs_game_one_running` on `(game_id) WHERE status='running'` — prevents duplicate running audits across processes.
- DB-level status guard: CHECK constraint on `status` for allowed values only.
- DB-level trigger-source guard: CHECK constraint on `trigger_source` for allowed values only.

**`AuditFlag`**
- `id` — PK
- `game_id` — FK → games
- `audit_run_id` — FK → audit_runs
- `flag_type` — VARCHAR: `entity_duplicate` | `missing_entity` | `missing_event` | `missing_decision` | `missing_loot` | `loot_correction` | `decision_correction` | `deletion_candidate` | `other`
- `target_type` — VARCHAR: `entity` | `quest` | `thread` | `loot` | `decision` | `note` (nullable)
- `target_id` — Integer (nullable) — ID of the record flagged
- `description` — Text — human-readable description of the issue
- `suggested_change` — JSONB — machine-readable proposed correction
- `status` — VARCHAR: `pending` | `applied` | `dismissed`
- `created_at` — timestamp (default now)
- `resolved_at` — timestamp (nullable)
- DB-level status guard: CHECK constraint on `status` for allowed values only.

> **Note:** For `entity_duplicate` flags, `target_id` = duplicate entity ID; canonical entity ID is stored in `suggested_change.canonical_id`.

> **Note:** `loot_correction` and `decision_correction` flag types in `audit_flags` are reserved for *genuinely ambiguous* cases the LLM cannot resolve from transcript evidence alone. Confident corrections go into the high-confidence `loot_corrections` / `decision_corrections` fields in `AuditOutput` (Phase 2) and are auto-applied.

### Modifications to existing ORM models in `src/foundry_bridge/models.py`

**`Note`**
- Add `is_audit` boolean column (default `False`). Synthetic audit notes will have `is_audit=True`.

**`Quest` and `Thread`**
- Add soft-delete fields used by `deletion_candidate` workflows:
  - `is_deleted` boolean (default `False`)
  - `deleted_at` timestamp (nullable)
  - `deleted_reason` text (nullable)

### New migration: `alembic/versions/0010_add_audit_tables.py`

Creates:
- `audit_runs` table with indexes on `(game_id)`, `(status)`
- `audit_flags` table with indexes on `(game_id, status)`, `(audit_run_id)`
- JSONB column for `suggested_change` (avoids Postgres enum management overhead)
- CHECK constraints for `audit_runs.status` and `audit_flags.status`
- CHECK constraint for `audit_runs.trigger_source`
- Soft-delete columns on `quests` and `threads` (`is_deleted`, `deleted_at`, `deleted_reason`)

> **Migration note:** The `audit_runs.audit_note_id` FK column (→ `notes.id`) must be included in this migration. Also add `is_audit BOOLEAN NOT NULL DEFAULT FALSE` to the existing `notes` table. Also add a **partial UNIQUE constraint**: `CREATE UNIQUE INDEX uq_audit_runs_game_one_running ON audit_runs(game_id) WHERE status = 'running'`. This prevents two `running` audit runs from existing for the same game simultaneously, even across process restarts or crashes.

---

## Phase 2 — Audit Generator (`src/foundry_bridge/audit_generator.py`)

New file modeled after `note_generator.py`. Uses the same LangGraph ReAct pattern as `note_generator.py`: `create_agent` with bound tools, then a structured output extraction prompt. `_MODEL_STR` is read from the same `MODEL_PROVIDER`/`MODEL` env vars.

`audit_generator.py` imports and calls `validate_config()` from `note_generator.py` at startup (same LLM API key check, same env vars). No separate `validate_audit_config()` needed.

### `AuditOutput` Pydantic schema

**High-confidence (auto-apply):**
```python
entity_description_updates: list[EntityDescriptionUpdate]
# {entity_id: int, new_description: str, reason: str}

quest_description_updates: list[QuestDescriptionUpdate]
# {quest_id: int, new_description: str, reason: str}

quest_status_updates: list[QuestStatusUpdate]
# {quest_id: int, new_status: Literal["active", "completed"], reason: str}

thread_resolutions: list[ThreadResolution]
# {thread_id: int, resolution_text: str}

new_entities: list[EntityOutput]
# missed extractions: {entity_type, name, description}

new_events: list[str]
# missed events

new_decisions: list[NewDecision]
# {decision: str, made_by: str, reason: str} — missed decision extractions

new_loot: list[NewLootItem]
# {item_name: str, acquired_by: str, quest_id: int | None, reason: str} — missed loot extractions

new_quests: list[QuestOutput]
# missed quest extractions (same structure as note_generator quests_opened)

new_threads: list[ThreadOutput]
# {text: str, quest_id: int | None} — quest_id MUST be looked up via search_quests before use

new_quotes: list[ImportantQuoteOutput]
# missed important quote extractions {text: str, transcript_id: int | None, speaker: str | None}

new_combat: list[CombatUpdate]
# {encounter: str, outcome: str} — missed combat encounters

thread_text_updates: list[ThreadTextUpdate]
# {thread_id: int, new_text: str, reason: str} — for correcting incorrectly extracted thread text

event_text_updates: list[EventTextUpdate]
# {event_id: int, new_text: str, reason: str} — for correcting event text

decision_corrections: list[DecisionCorrection]
# {decision_id: int, new_decision: str, new_made_by: str, reason: str} — for fixing attribution/text errors

loot_corrections: list[LootCorrection]
# {loot_id: int, new_item_name: str, new_acquired_by: str, reason: str} — for fixing attribution errors

quote_corrections: list[QuoteCorrection]
# {quote_id: int, new_text: str, new_speaker: str, reason: str} — for fixing misattributed/mangled quotes
```

**Low-confidence (flagged for human review):**
```python
audit_flags: list[AuditFlagOutput]
# {flag_type, target_type, target_id (optional), description, suggested_change (dict)}
```

> **Note:** `missing_decision` and `missing_loot` are confidence-routed: they are emitted as high-confidence creates when transcript evidence is unambiguous, and emitted as `audit_flags` when evidence is ambiguous.

> **Note:** `audit_flags` of type `deletion_candidate` are used when the agent identifies a row it believes should be removed. The agent must call the relevant search tool first to confirm the record exists before flagging it for deletion.

> **Note:** The audit agent is the authoritative correction and gap-filling service for all derived data: it can create, update, and merge any derived data type except transcripts (which are raw input and immutable).

### Tools (all 9 from `note_generator.py` + 3 new listing tools)

Inherited search tools:
1. `search_quests`
2. `search_entities`
3. `search_open_threads`
4. `search_resolved_threads`
5. `search_events`
6. `search_past_notes`
7. `search_decisions`
8. `search_loot`
9. `search_combat`

New listing tools (bound per `game_id`):
10. `get_all_entities` → list `{id, name, entity_type}` — for duplicate detection
11. `get_all_quests` → list `{id, name, status}` — for completeness check
12. `get_all_open_threads` → list `{id, text}` — for resolution detection

> Tools 10–12 are callable tools the agent invokes on-demand (not pre-loaded context). They are bound per `game_id` at runtime.

> **Context preamble vs. tool calls:** The lightweight context preamble is NOT a substitute for tool calls — the agent must still call search/listing tools to get IDs, descriptions, and other details needed to fill AuditOutput fields.

### System prompt focus
- Review consistency between transcripts and all existing structured data
- Flag obvious errors (wrong attribution, stale description) as high-confidence
- Flag ambiguous duplicates or uncertain changes as low-confidence audit flags
- Search before creating new entities/quests (same discipline as note_generator)
- Do not hallucinate; only assert corrections supported by transcript evidence
- **Confidence thresholds:** use high-confidence (auto-apply) outputs ONLY when the transcript contains unambiguous evidence. Use `audit_flags` for anything ambiguous, inferred, or where you are unsure. When in doubt, flag — do not auto-apply.
- **Focus on high-impact corrections only.** Prioritize: factually wrong data (wrong character attributions, incorrect quest status, clearly stale descriptions), structural gaps (missing quests, unresolved threads with clear transcript evidence), entity duplicates. Skip minor wording improvements, stylistic rewrites, or speculative corrections not directly supported by transcript evidence. The goal is correctness, not completeness of every minor detail.
- Before setting `quest_id` on any `new_threads` entry, the agent MUST call `search_quests` to look up the correct quest ID — same rule as in `note_generator`. Do NOT guess or invent quest IDs.
- **Before outputting any correction or creation**, the agent MUST use the relevant search tools to confirm the target entity/quest/thread/loot/decision/event/etc. actually exists. For updates: confirm the record is present. For creates: confirm it doesn't already exist (to avoid creating duplicates). This applies to ALL output types.
- **Confidence threshold for new entities:** Put a newly-identified entity in `new_entities` (auto-applied) ONLY when the transcript unambiguously confirms its existence, name, and type. Use `audit_flags` with type `missing_entity` when the entity name, type, or existence is ambiguous from transcript evidence (e.g. a referenced name that could be a person or place, or a suspected NPC whose role is unclear).
- **Quote correction fallback matching:** when `transcript_id` is unavailable, allow auto-correction only when quote text matches the transcript window using case-insensitive, whitespace-normalized exact matching.
- **Search scope rule:** semantic/listing/search tools exclude soft-deleted quests/threads by default.

> **Tool-use rule:** Before outputting any `loot_corrections` entry, call `search_loot` to verify the loot item exists and confirm the correct current `acquired_by`. Before outputting any `decision_corrections` entry, call `search_decisions` to verify the decision exists. Before outputting any `quote_corrections` entry, call `search_past_notes` or confirm from transcript context.

### Key function
```python
async def generate_audit(
    game_id: int,
    transcripts: list[Transcript],
    player_characters: list[PlayerCharacter],
) -> AuditOutput
```

> **Transcript format:** Transcripts are formatted identically to `note_generator`: `[ID:N][SPEAKER]: text`, concatenated in `turn_index` order.

> **Error handling:** Imports `GraphRecursionError` from `langgraph.errors`. If the agent graph exceeds its recursion limit, `GraphRecursionError` is raised — the caller (`auditor.py`) must handle it.

> **Context preamble:** Before invoking the agent, `generate_audit` builds a **context preamble** injected into the user-facing message (not the system prompt):
> - Entity count by type + list of entity names
> - Quest names + statuses
> - Open thread count + list of thread texts (truncated if very long)
> - Player character names
>
> This gives the agent a quick orientation to what already exists, so it knows approximately what to search for without having to call `get_all_entities` upfront. Full details (descriptions, quest text, thread text) are fetched on-demand via tools.

---

## Phase 3 — DB Audit Functions (`src/foundry_bridge/db.py`)

New functions to add:

**Read:**
- `get_last_audit_run_for_game(game_id)` → `AuditRun | None` — Only returns runs with `status='completed'`. Failed or running audit runs are ignored for window calculation purposes.
- `get_notes_since_last_audit(game_id, since_note_id: int | None)` → `list[Note]` — Returns all notes for `game_id` with `id > since_note_id` (when `since_note_id` is provided). If `since_note_id` is `None` (no completed audit exists), returns ALL notes for the game. Notes are returned in ascending `id` order.
- `get_transcripts_for_notes(note_ids: list[int])` → `list[Transcript]` — fetches rows whose IDs appear in any `note.source_transcript_ids` ARRAY
- `get_unaudited_note_count(game_id)` → `int` — count of notes with id > last audit run's max note ID
- `get_all_entities_for_game(game_id)` → `list[dict]` — lightweight `{id, name, entity_type}`
- `get_all_quests_for_game(game_id)` → `list[dict]` — `{id, name, status}`
- `get_all_open_threads_for_game(game_id)` → `list[dict]` — lightweight `{id, text}` for all open (unresolved) threads for a game. Used by listing tool #12.

**Write:**
- `create_audit_run(game_id, trigger_source: str) → AuditRun` — creates pre-run row with `status='running'`, `audit_note_id=NULL`
- `touch_audit_run_heartbeat(audit_run_id) -> None` — updates `heartbeat_at` during execution
- `restore_deleted_quest(game_id, quest_id) -> Quest` — clears soft-delete fields
- `restore_deleted_thread(game_id, thread_id) -> Thread` — clears soft-delete fields

**`AuditPipelineResult` dataclass (defined in `db.py`):**  
A `dataclass` or `TypedDict` returned by `write_audit_pipeline_result` and consumed by `_write_audit_embeddings`. Holds ORM objects (with IDs populated by DB) for all rows created/updated during the audit:
- `updated_entities: list[Entity]` — from entity_description_updates
- `new_entities: list[Entity]` — from new_entities
- `updated_events: list[Event]` — from event_text_updates (successfully updated only)
- `new_events: list[Event]` — from new_events
- `updated_threads: list[Thread]` — from thread_text_updates + thread_resolutions
- `updated_decisions: list[Decision]` — from decision_corrections
- `new_decisions: list[Decision]` — from new_decisions
- `updated_loot: list[Loot]` — from loot_corrections (successfully updated)
- `new_loot: list[Loot]` — from new_loot
- `updated_quests: list[Quest]` — from quest_description_updates + quest_status_updates
- `new_quests: list[Quest]` — from new_quests
- `new_threads: list[Thread]` — from new_threads
- `new_combat: list[CombatUpdate]` — from new_combat
- `synthetic_note: Note` — the audit note created in Step 1

> **Note:** Since the entire write is atomic, the AuditPipelineResult is populated fully on commit or not at all. `_write_audit_embeddings` is called after the commit.

- `write_audit_pipeline_result(game_id, audit_run_id: int, output: AuditOutput, notes: list[Note]) → AuditPipelineResult` — **multi-phase write — all writes in a single `async with session.begin()` transaction (Phases A/B/C). If any step fails, the entire transaction rolls back and `fail_audit_run` is called.** Returns an `AuditPipelineResult` (see above).

  **Step 1 (own transaction — runs first):** Create a synthetic `Note` row with `summary=f'Audit: {len(output.entity_description_updates)} entity updates, {len(output.new_entities)} new entities, {len(output.new_quests)} new quests, {len(output.new_threads)} new threads, {len(output.audit_flags)} flags'`, `source_transcript_ids = sorted(set(id for note in notes for id in note.source_transcript_ids))` (deduplicated union of all `source_transcript_ids` across all notes in the audit window), and `is_audit=True`. Store the resulting ID as `audit_note_id`. If this fails, mark the pre-created `audit_run_id` as failed with `audit_note_id=NULL`, then raise.

  **Step 2 (start of main transaction):** Update the pre-created `AuditRun` row (`id=audit_run_id`) to set `audit_note_id=<note from Step 1>`. Phases A/B/C continue within this same `session.begin()` transaction.

  > **Note:** `fail_audit_run` is called in the exception handler if any step from Step 2 onward fails and the transaction rolls back.

  **Phase A (corrections):**
  3. Apply `entity_description_updates` (`UPDATE entities SET description=...`)
  4. Apply `quest_description_updates` + archive old description in `quest_description_history`. When archiving to `quest_description_history`, set `note_id = audit_note_id` (the synthetic note created in Step 1).
  5. Apply `quest_status_updates` (`UPDATE quests SET status=...`)
  6. Apply `thread_resolutions` (mark `is_resolved=True`, set `resolution`, `resolved_at=now()`, `resolved_by_note_id=audit_note_id`)
  7. Apply `thread_text_updates` (`UPDATE threads SET text=new_text WHERE id=thread_id`)
  8. Apply `event_text_updates` (`UPDATE events SET text=new_text WHERE id=event_id`). Events have a `UniqueConstraint(game_id, text)`. UPDATE in-place is used — PostgreSQL automatically updates the unique index. If `new_text` already exists in the events table for this game, the UPDATE will raise a `UniqueViolation`. Wrap in try/except: log a warning and skip the update (old event row stays as-is) to avoid data loss.
  9. Apply `decision_corrections` (`UPDATE decisions SET decision=new_decision, made_by=new_made_by WHERE id=decision_id`)
  10. Apply `loot_corrections` (`UPDATE loot SET item_name=new_item_name, acquired_by=new_acquired_by WHERE id=loot_id`). Handle potential `UniqueConstraint(game_id, item_name, acquired_by)` violation: wrap in `try/except` and skip with a warning log if the target already exists.
  11. Apply `quote_corrections` (`UPDATE important_quotes SET text=new_text, speaker=new_speaker WHERE id=quote_id`)

  **Phase B (new data):**

  > **Ordering within Phase B:** `new_quests` must be written before `new_threads`. Since both occur in the same transaction, call `session.flush()` after inserting new quests to make their PKs visible for thread's `quest_id` FK validation — same pattern as `write_note_pipeline_result`. The ordering within Phase B is: new_entities → new_events → new_decisions → new_loot → new_quests → (flush) → new_threads → new_quotes → new_combat.

  12. Upsert `new_entities` — insert `notes_entities` entries referencing `audit_note_id`; Upsert `new_events` — insert `notes_events` entries referencing `audit_note_id`
  13. Insert `new_decisions` — link to `audit_note_id`; these are new Decision rows with `note_id=audit_note_id`
  14. Upsert `new_loot` — same UniqueConstraint handling as note pipeline (`game_id, item_name, acquired_by`). After upserting each `new_loot` item, insert a `notes_loot` row linking `(audit_note_id, loot_id)` — same pattern as the note pipeline.
  15. Upsert `new_quests` — same logic as note pipeline `quests_opened`; archive description history if quest already exists. Set `note_ids = [audit_note_id]` on creation. If quest already exists (upsert ON CONFLICT), append `audit_note_id` to the existing `note_ids` array (same as note pipeline's quest update logic).
  16. Insert `new_threads` — link to `audit_note_id` via `opened_by_note_id`
  17. Insert `new_quotes` — link to `audit_note_id` as the `note_id` FK
  18. Insert `new_combat` — link to `audit_note_id`

  **Phase C (flags + finalization):**
  19. Insert `audit_flags` records
  20. `UPDATE audit_runs SET status='completed', completed_at=now(), notes_audited=..., notes_audited_count=..., min_note_id=..., max_note_id=...`.

  > **Failure semantics:** All Phase A/B/C writes are in a single `async with session.begin()` transaction. If any step fails, the entire transaction rolls back and `fail_audit_run` is called. Step 1 (synthetic note) still runs outside the main transaction so `audit_note_id` can be linked to the pre-created run. If Step 2+ fails after Step 1 succeeded, delete the synthetic audit note as cleanup (no orphan audit notes). **Because the write is fully atomic, a failed audit run leaves no partial writes. The note window for the next audit is unaffected (same transcripts will be re-audited on the next trigger).**

  > **Embedding timing:** `_write_audit_embeddings` is called after the single transaction commits, using the `AuditPipelineResult`. Same pattern as `_write_embeddings_for_pipeline_result` in the note pipeline.
- `fail_audit_run(audit_run_id)` — `UPDATE audit_runs SET status='failed'`
- `reset_stale_audit_runs(stale_after_minutes: int = 15)` — `UPDATE audit_runs SET status='failed' WHERE status='running' AND (heartbeat_at IS NULL OR heartbeat_at < now() - interval '<stale_after_minutes> minutes')`. Called at server startup and by periodic sweeper. Applies across ALL games (no `game_id` filter).
- `_write_audit_embeddings(result: AuditPipelineResult) -> None` — Computes and writes embeddings for ALL rows touched by this audit run that have embedding columns:
  - Entities: from `entity_description_updates` (updated) + `new_entities` (created)
  - Events: from `event_text_updates` (updated) + `new_events` (created)
    > For `event_text_updates`, only re-embed events that were successfully updated (skip events where the UniqueViolation caused the update to be skipped).
  - Threads: from `thread_text_updates` (updated) + `thread_resolutions` (resolved threads, if they have embeddings) + `new_threads` (created)
  - Decisions: from `decision_corrections` (updated) + `new_decisions` (created)
  - Loot: from `loot_corrections` (updated) + `new_loot` (created)
  - Quests: from `quest_description_updates` (updated) + `quest_status_updates` (updated) + `new_quests` (created)
  - Combat: `new_combat` (created)
  - The synthetic audit Note: embedding of its summary
  - `new_quotes` — **excluded**: `ImportantQuote` has no `embedding` column in the current model. If an embedding column is added to `ImportantQuote` in a future migration, update this function.

  All embeddings are computed post-commit (same pattern as `_write_embeddings_for_pipeline_result` in the note pipeline). If embedding writes fail post-commit, keep committed rows and retry in background with bounded exponential backoff (`5s`, `15s`, `45s`, max 3 attempts), then log and stop.

#### Research: Embedding column audit (`src/foundry_bridge/models.py`)

**Models WITH `embedding` columns:**
- `Entity` (line 88)
- `Thread` (line 106)
- `Event` (line 133)
- `Decision` (line 167)
- `Loot` (line 179)
- `Note` (line 190)
- `Quest` (line 214)
- `CombatUpdate` (line 271)

**Models WITHOUT `embedding` columns:**
- `ImportantQuote` — no embedding column (excluded from `_write_audit_embeddings`)
- `QuestDescriptionHistory` — no embedding
- `PlayerCharacter` — no embedding
- `Transcript` — no embedding
- `Game` — no embedding

**Flag apply/dismiss:**
- `apply_audit_flag(flag_id)` — reads `suggested_change` JSON and dispatches update to the right table; sets `status='applied'`, `resolved_at=now()`
  - For `entity_duplicate` flags: `suggested_change = {"canonical_id": int, "duplicate_id": int}`. The dispatcher reads both IDs. **Full merge (atomic transaction):**
    1. `UPDATE quests SET quest_giver_entity_id = canonical_id WHERE quest_giver_entity_id = duplicate_id`
    2. For `notes_entities` (unique constraint on `(note_id, entity_id)`): `INSERT INTO notes_entities(note_id, entity_id) SELECT note_id, canonical_id FROM notes_entities WHERE entity_id = duplicate_id ON CONFLICT DO NOTHING`, then `DELETE FROM notes_entities WHERE entity_id = duplicate_id`
    3. `DELETE FROM entities WHERE id = duplicate_id`
    
    After deletion, set `status='applied'`, `resolved_at=now()`.

  - For `deletion_candidate` flags on `entities` table: **Atomic transaction:**
    1. `UPDATE quests SET quest_giver_entity_id = NULL WHERE quest_giver_entity_id = record_id`
    2. `DELETE FROM notes_entities WHERE entity_id = record_id` (delete manually, or rely on `ON DELETE CASCADE` if configured)
    3. `DELETE FROM entities WHERE id = record_id`

  **`suggested_change` JSONB shapes by `flag_type`:**

  | `flag_type` | Shape | Dispatch action |
  |---|---|---|
  | `entity_duplicate` | `{"canonical_id": int, "duplicate_id": int}` | Full merge (FK reassignment + delete duplicate) — documented above |
  | `missing_entity` | `{"name": str, "entity_type": str, "description": str}` | INSERT entity (upsert), then INSERT `notes_entities` row linking to the flag's `audit_run.audit_note_id` |
  | `missing_event` | `{"text": str}` | INSERT event (upsert) |
  | `missing_decision` | `{"decision": str, "made_by": str}` | INSERT decision linked to `audit_run.audit_note_id` |
  | `missing_loot` | `{"item_name": str, "acquired_by": str}` | UPSERT loot + link via `notes_loot` to `audit_run.audit_note_id` |
  | `loot_correction` | `{"loot_id": int, "new_item_name": str, "new_acquired_by": str}` | UPDATE loot SET item_name, acquired_by; handle `UniqueConstraint` violation: skip with warning |
  | `decision_correction` | `{"decision_id": int, "new_decision": str, "new_made_by": str}` | UPDATE decisions SET decision, made_by |
  | `deletion_candidate` | `{"table": str, "record_id": int, "reason": str}` | For `quests`/`threads`: soft-delete (`is_deleted=true`, `deleted_at=now()`, `deleted_reason=reason`). For `entities`: atomic FK cleanup + delete. For `events`, `loot`, `decisions`, `important_quotes`: hard delete. |
  | `other` | `{"description": str, "proposed_action": str}` | No-op (human has already taken manual action); just set `status='applied'`, `resolved_at=now()` |

  > **Note:** For `missing_entity` dispatch, `apply_audit_flag` must look up the `audit_run_id` on the flag to find the `audit_note_id` for the `notes_entities` row.

- `dismiss_audit_flag(flag_id)` — sets `status='dismissed'`, `resolved_at=now()`
- `reopen_audit_flag(flag_id)` — idempotent: sets `status='pending'`, clears `resolved_at` when needed; if already pending, return unchanged row with `noop=true` metadata.

---

## Phase 4 — Auditor Task (`src/foundry_bridge/auditor.py`)

New file.

### Config
```python
AUDIT_AFTER_N_NOTES = int(os.environ.get("AUDIT_AFTER_N_NOTES", "5"))
```

> **Startup note:** On module load, `auditor.py` does NOT call `validate_config()` — this is already handled by `note_taker.py` startup sequence which runs at server start.

### Startup cleanup
```python
async def reset_stale_audit_runs():
  """Mark stale 'running' audit_runs as 'failed'. Uses heartbeat and 15-minute staleness window."""
  # UPDATE ... WHERE status='running' AND heartbeat_at older than threshold
```

Call this function from the FastAPI lifespan hook in `server.py` or `api.py`, **before** the note polling loop starts, and run a periodic sweeper every 5 minutes.

> **Atomic guarantee:** Since the write is fully atomic (see Phase 3), a failed-then-reset audit run will have committed zero data. Marking it failed simply allows the next note pipeline completion to re-trigger the audit.

### Per-game lock
Import from `src/foundry_bridge/locks.py` (a new shared module). Both `note_taker.py` and `auditor.py` import `_game_locks` from it, resolving the circular import.

`locks.py` exports:
- `_game_locks: dict[int, asyncio.Lock]` — per-game lock registry
- `def get_game_lock(game_id: int) -> asyncio.Lock` — retrieves or creates a lock for the given game

### Core async function
```python
async def _run_audit_pipeline(game_id: int, audit_run_id: int, force: bool = False):
    # 1. Acquire per-game lock via get_game_lock(game_id). If locked, skip (note pipeline may be running).
    # 2. (Inside lock) Call embed_unembedded_rows(game_id) — ensures all rows have current embeddings
    #    before the LLM agent runs semantic searches. Consistent with note_taker pattern.
    # 3. get_last_audit_run_for_game(game_id) → returns last *completed* audit run only.
    #    since_note_id = max(notes_audited) from that run, or None if no completed run exists.
    # 4. get_notes_since_last_audit(game_id, since_note_id) → list[Note]
    # 5. Collect ALL source_transcript_ids from notes in window (de-dup).
    #    Pass the full notes list into write_audit_pipeline_result for the synthetic note union.
    # 6. get_transcripts_for_notes(transcript_ids) — ordered by turn_index
    # 7. get_player_characters_for_game(game_id)
    # 8. generate_audit(game_id, transcripts, player_characters) → AuditOutput
    # 9. pipeline_result = await write_audit_pipeline_result(..., audit_run_id=audit_run_id) — creates synthetic note,
    #    updates the pre-created AuditRun, then runs all phase A/B/C writes.
    # 10. await _write_audit_embeddings(pipeline_result) — post-commit embedding pass with retry backoff
    # 11. On general exception before synthetic note creation, delete the pre-created run row.
    #     On failures from write_audit_pipeline_result (step 9) or later, fail_audit_run is handled internally.
    # 12. On GraphRecursionError (from generate_audit, step 8), mark run failed and return.
```

> **Runtime note:** Create named background tasks for audit runs and attach done-callback exception logging for observability.
> **Heartbeat runtime note:** In addition to phase-based heartbeat updates, run a fallback heartbeat tick every 60 seconds during long-running LLM/tool steps.
  > **Sweeper runtime note:** Periodic sweeper runs in all long-running processes, applies random startup jitter (`0-30s`), and skips games with held in-process lock.

### Hook into note_taker
```python
async def check_and_trigger_audit(game_id: int):
    count = await get_unaudited_note_count(game_id)
    if count >= AUDIT_AFTER_N_NOTES:
  # pre-create running AuditRun with trigger_source='auto'
  asyncio.create_task(_run_audit_pipeline(game_id, audit_run_id=created_run.id, force=False))
```

> **Caller contract note:** threshold checks stay in caller logic; shared precreate helper only creates rows.

Called in `note_taker._run_pipeline()` after `write_note_pipeline_result()` succeeds.

> **Locking rollout note:** Move per-game locks into `src/foundry_bridge/locks.py` before introducing `auditor.py`, so both pipelines share one lock source from day one.

---

## Phase 5 — API Endpoints (`src/foundry_bridge/api.py`)

### New Pydantic schemas
> **Note:** The existing `NoteOut` schema in `api.py` should be updated to include `is_audit: bool` to reflect the new column on the `Note` model.

> **Note:** The existing `GET /api/games/{game_id}/notes` endpoint returns ALL notes including `is_audit=True` synthetic notes. No server-side filtering is added. Frontends use the `is_audit` field to distinguish and style/hide them as appropriate.

```python
class AuditRunOut(BaseModel):
    id: int
    game_id: int
    triggered_at: datetime
    completed_at: datetime | None
    status: str
    trigger_source: str
    notes_audited: list[int]
    notes_audited_count: int
    min_note_id: int | None
    max_note_id: int | None
    heartbeat_at: datetime | None
    audit_note_id: int | None
    model_config = ConfigDict(from_attributes=True)

class AuditFlagOut(BaseModel):
    id: int
    game_id: int
    audit_run_id: int
    flag_type: str
    target_type: str | None
    target_id: int | None
    description: str
    suggested_change: dict
    status: str
    created_at: datetime
    resolved_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

class AuditFlagMutationOut(BaseModel):
    flag: AuditFlagOut
    noop: bool = False
  reason_code: str | None = None
    message: str | None = None

class AuditRunTriggerOut(BaseModel):
  run: AuditRunOut | None
    noop: bool = False
  reason_code: str | None = None
    message: str | None = None
```

> **Query params:** The `GET /audit-flags` endpoint accepts `limit: int = 50` and `offset: int = 0` query params for pagination.

### New routes
`check_and_trigger_audit` logic is shared/reusable — the manual trigger endpoint below also calls `_run_audit_pipeline` directly rather than duplicating the threshold check.

```
GET  /api/games/{game_id}/audit-runs
     → list[AuditRunOut], newest first

POST /api/games/{game_id}/audit-runs/trigger
  → Creates `audit_runs` row immediately with `status='running'`, returns `AuditRunTriggerOut`, then triggers _run_audit_pipeline(game_id, audit_run_id=run.id, force=<bool>) as asyncio task
     → 409 Conflict if an audit is already running for this game. The endpoint performs two checks:
       1. Query `audit_runs WHERE game_id=? AND status='running'` — catches audits started in any process
       2. Check `get_game_lock(game_id).locked()` — catches an in-flight lock in the current process
       If either check is true, return 409.
     → Also handles DB partial-unique-index conflict as a final race-condition guard.
  → Supports `force=true` query param for manual runs even when unaudited note count is zero.
    → If `force=false` and unaudited note count is zero: returns `200` with `noop=true`, `run=null`, and canonical message.
  → Includes machine-readable `reason_code` in wrapper responses.
    → For conflict/error responses (for example `409`), include `X-Reason-Code` header while keeping standard `detail` body text.

GET  /api/games/{game_id}/audit-flags?status=pending&offset=0&limit=50
     → list[AuditFlagOut], filtered by status (optional), paginated

POST /api/games/{game_id}/audit-flags/{flag_id}/apply
     → AuditFlagMutationOut (`flag.status=applied`)
     → Idempotent: if already applied, returns unchanged row with `noop=true`
  → Includes machine-readable `reason_code` in wrapper responses.

POST /api/games/{game_id}/audit-flags/{flag_id}/dismiss
     → AuditFlagMutationOut (`flag.status=dismissed`)
     → Idempotent: if already dismissed, returns unchanged row with `noop=true`
  → Includes machine-readable `reason_code` in wrapper responses.

POST /api/games/{game_id}/audit-flags/{flag_id}/reopen
     → AuditFlagMutationOut (`flag.status=pending`)
     → Resets a previously applied or dismissed flag back to pending status
     → Idempotent: if already pending, returns unchanged row with `noop=true` metadata
  → Includes machine-readable `reason_code` in wrapper responses.

POST /api/games/{game_id}/quests/{quest_id}/restore
  → Restores a soft-deleted quest (`is_deleted=false`, `deleted_at=NULL`, `deleted_reason=NULL`)

POST /api/games/{game_id}/threads/{thread_id}/restore
  → Restores a soft-deleted thread (`is_deleted=false`, `deleted_at=NULL`, `deleted_reason=NULL`)

GET  /api/entities/{entity_id}
     → AuditEntityOut (or the existing EntityOut schema)
     → Returns 404 if entity not found
     (Required by the FlagCard frontend component for entity_duplicate flags.)
```

### Modified existing endpoints

**`DELETE /api/notes/{id}`**
- Returns **409 Conflict** if `note.is_audit = True`. Audit notes cannot be manually deleted via the API.
- This guard runs before the existing delete logic.

---

## Phase 6 — Frontend Types (`frontend/src/types.ts`)

Add the following type definitions to `frontend/src/types.ts`:

```typescript
export type FlagType =
  | "entity_duplicate"
  | "missing_entity"
  | "missing_event"
  | "missing_decision"
  | "missing_loot"
  | "loot_correction"
  | "decision_correction"
  | "deletion_candidate"
  | "other";

export type FlagStatus = "pending" | "applied" | "dismissed";

export type ReasonCode =
  | "conflict_running"
  | "noop_no_new_notes"
  | "schedule_failed"
  | "precreate_failed"
  | "early_pipeline_failure";

export interface AuditRun {
  id: number;
  game_id: number;
  triggered_at: string;
  heartbeat_at: string | null;
  completed_at: string | null;
  status: "running" | "completed" | "failed";
  trigger_source: "auto" | "manual";
  notes_audited: number[];
  notes_audited_count: number;
  min_note_id: number | null;
  max_note_id: number | null;
  audit_note_id: number | null;
}

export interface AuditFlag {
  id: number;
  game_id: number;
  audit_run_id: number;
  flag_type: FlagType;
  target_type: string | null;
  target_id: number | null;
  description: string;
  suggested_change: Record<string, unknown>;
  status: FlagStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditFlagMutation {
  flag: AuditFlag;
  noop: boolean;
  reason_code: ReasonCode | null;
  message: string | null;
}

export interface AuditRunTrigger {
  run: AuditRun | null;
  noop: boolean;
  reason_code: ReasonCode | null;
  message: string | null;
}
```

Also add `is_audit: boolean` to the existing `Note` interface.

---

## Phase 7 — Frontend Implementation

### Files changed

| File | Change |
|------|--------|
| `frontend/src/types.ts` | (already in Phase 6) |
| `frontend/src/api.ts` | Add audit API functions |
| `frontend/src/pages/GameDetail.tsx` | Add Audit tab to `TABS` array + route + NavLink badge |
| `frontend/src/pages/tabs/AuditTab.tsx` | **NEW** — main audit tab component |
| `frontend/src/pages/tabs/NotesTab.tsx` | Modify `NoteCard` to handle `is_audit` notes |
| `frontend/src/components/Toast.tsx` | **NEW** — minimal inline toast component for undo notifications |

---

### `api.ts` additions

Add the following functions to `frontend/src/api.ts`:

```typescript
// ── Audit ──────────────────────────────────────────────────────────────────
export const getAuditRuns = (gameId: number) =>
  api.get<AuditRun[]>(`/games/${gameId}/audit-runs`).then(r => r.data);

export const triggerAudit = (gameId: number, force = false) =>
  api.post<AuditRunTrigger>(`/games/${gameId}/audit-runs/trigger`, null, { params: { force } }).then(r => r.data);

export const getAuditFlags = (gameId: number, status?: FlagStatus, offset = 0, limit = 50) =>
  api.get<AuditFlag[]>(`/games/${gameId}/audit-flags`, { params: { ...(status ? { status } : {}), offset, limit } }).then(r => r.data);

export const applyAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/apply`).then(r => r.data);

export const dismissAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/dismiss`).then(r => r.data);

export const reopenAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/reopen`).then(r => r.data);

export const getEntity = (entityId: number) =>
  api.get<Entity>(`/entities/${entityId}`).then(r => r.data);
```

> **Note:** The `AuditFlag` object already carries `game_id`, so callers can derive `gameId` from flag data when needed. The function signatures for `applyAuditFlag`, `dismissAuditFlag`, and `reopenAuditFlag` require both `gameId` and `flagId` explicitly to match the nested API route shape.

---

### `GameDetail.tsx` changes

1. **Imports to add:**
   - `ClipboardCheck` from `lucide-react`
   - `AuditTab` from `'./tabs/AuditTab'`
   - `getAuditFlags` from `'../../api'`

2. **Add to `TABS` array** (at the end, after `characters`):
   ```typescript
   { id: 'audit', label: 'Audit', icon: ClipboardCheck }
   ```

3. **Add route** inside the `<Routes>` block:
   ```tsx
   <Route path="audit" element={<AuditTab gameId={gameId} />} />
   ```

4. **Fetch pending flag count** at `GameDetail` level (so the badge reflects live data without loading the full `AuditTab`):
   ```typescript
   const { data: pendingFlags = [] } = useQuery({
     queryKey: ['audit-flags', gameId, 'pending'],
     queryFn: () => getAuditFlags(gameId, 'pending'),
   });
   ```
   > **Note:** The pending flag badge query is intentionally fetched across all tabs so the Audit nav badge is always current. The query is cheap (status=pending filter + limit=50) and cached by React Query.

5. **NavLink badge:** Extend the `NavLink` rendering (or the local component that renders tab nav items) to accept an optional `badgeCount?: number` prop. For the Audit tab entry only, pass a capped value display (`50+` when pending hits page limit). When `badgeCount > 0`, render a small inline badge (e.g. `bg-red-600 text-white text-xs rounded-full px-1.5`) after the label text — following the same pattern as `NotesBadge.tsx`.

---

### `AuditTab.tsx` structure

New file at `frontend/src/pages/tabs/AuditTab.tsx`. Component breakdown:

#### `AuditTab({ gameId: number })`

Root component. Owns the status filter state and data fetching:

```tsx
const [statusFilter, setStatusFilter] = useState<FlagStatus | undefined>('pending');

const { data: runs = [] } = useQuery({
  queryKey: ['audit-runs', gameId],
  queryFn: () => getAuditRuns(gameId),
  refetchInterval: (data) => {
    const latest = data?.[0]
    return latest?.status === 'running' ? 10_000 : false
  }
});
```

When the latest run transitions from `running` to `completed`, invalidate all domain query keys explicitly. Track previous status in a `useRef` to detect the transition:
```typescript
const prevStatusRef = useRef<string | undefined>(undefined)
useEffect(() => {
  const latest = auditRuns[0]
  if (prevStatusRef.current === 'running' && latest?.status === 'completed') {
    // Invalidate all game-scoped queries after audit completes
    const keysToInvalidate = [
      ['entities', gameId],
      ['quests', gameId],
      ['threads', gameId],
      ['events', gameId],
      ['decisions', gameId],
      ['loot', gameId],
      ['combat', gameId],
      ['quotes', gameId],
      ['notes', gameId],
    ];
    keysToInvalidate.forEach(key => qc.invalidateQueries({ queryKey: key }));
  }
  prevStatusRef.current = latest?.status
}, [auditRuns])
```

```tsx
const { data: flags = [] } = useQuery({
  queryKey: ['audit-flags', gameId, statusFilter],
  queryFn: () => getAuditFlags(gameId, statusFilter),
});

const latestRun = runs[0] ?? null;
```

Renders:
```tsx
<AuditRunHeader latestRun={latestRun} flagCount={flags.length} gameId={gameId} />
<AuditFlagList flags={flags} gameId={gameId} statusFilter={statusFilter} onStatusChange={setStatusFilter} />
```

---

#### `AuditRunHeader({ latestRun, flagCount, gameId })`

Layout (matches the spec):
```
┌──────────────────────────────────────────────────────────────┐
│  Last Audit Run:  [status badge]  [triggered_at relative]    │
│  Notes audited: N  │  Flags found: N  │  [Run Audit Now btn] │
│  (disabled / spinner if status=running)                      │
└──────────────────────────────────────────────────────────────┘
```

Details:
- **Status badge** colored per run status: `running` = yellow, `completed` = green, `failed` = red.
- **`triggered_at` relative time**: display as e.g. "3 hours ago" — use a small helper or `date-fns/formatDistanceToNow` if already in the project.
- **Notes audited count**: `latestRun?.notes_audited.length ?? 0`.
- **Flags count**: `flagCount` prop (length of the current flags list).
- **"Run Audit Now" button**: icon `Sparkles` or `ScanLine` from `lucide-react`. Disabled and shows a spinner/loading text when `latestRun?.status === 'running'`.
- **triggerAudit mutation**:
  ```typescript
  const triggerMutation = useMutation({
    mutationFn: () => triggerAudit(gameId),
    onSuccess: () => {
      toast('Audit started');
      queryClient.invalidateQueries({ queryKey: ['audit-runs', gameId] });
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        toast('Audit already in progress');
      }
    },
  });
  ```

- **Empty state**: If `latestRun` is `undefined` (no runs yet), render: `'No audit runs yet. Run the first audit to review your campaign data for consistency.'` message + the **'Run Audit Now'** button (enabled). Do NOT hide the button — this is exactly when the user should trigger one.

---

#### `AuditFlagList({ flags, gameId, statusFilter, onStatusChange })`

- Renders filter tabs: **All / Pending / Applied / Dismissed** — clicking sets `statusFilter` to `undefined | 'pending' | 'applied' | 'dismissed'` respectively.
- Shows a pending count badge next to the "Pending" tab label when `statusFilter !== 'pending'` (optional quality-of-life).
- Renders a `<FlagCard>` for each flag in `flags`.
- **Empty state**: When `flags.length === 0` for the current filter, render a per-filter message (same centered muted style as other tabs):
  - `pending`: `'No pending flags — all issues have been reviewed.'`
  - `applied`: `'No corrections have been applied yet.'`
  - `dismissed`: `'No flags have been dismissed yet.'`
  - `all` / `undefined`: `'No audit flags yet. Run an audit to review your campaign data.'`
- **Pagination**: Uses load-more (offset-based) pagination. `AuditFlagList` keeps a local `offset` state starting at 0. Calls `getAuditFlags(gameId, statusFilter, offset, 50)`. Shows a "Load more" button when the last page returned exactly 50 items. On Load More, increments `offset` by 50 and appends results to the existing list. Resetting `statusFilter` resets `offset` to 0.

---

#### `FlagCard({ flag, gameId })`

Layout:
```
┌─────────────────────────────────────────────────────┐
│ [flag_type badge]  [target_type + target_id pill]    │
│                                                      │
│  description text                                    │
│                                                      │
│  Suggested change (rendered by SuggestedChangeView)  │
│                                                      │
│  [Apply]  [Dismiss]  (or [Applied ✓] / [Dismissed]) │
└─────────────────────────────────────────────────────┘
```

**`flag_type` badge colors** — use `FLAG_TYPE_COLORS` (same convention as `TYPE_COLORS` in `EntitiesTab.tsx`):

```typescript
const FLAG_TYPE_COLORS: Record<FlagType, string> = {
  entity_duplicate:    'bg-purple-900 text-purple-200',
  missing_entity:      'bg-emerald-900 text-emerald-200',
  missing_event:       'bg-emerald-900 text-emerald-200',
  missing_decision:    'bg-emerald-900 text-emerald-200',
  missing_loot:        'bg-emerald-900 text-emerald-200',
  loot_correction:     'bg-blue-900 text-blue-200',
  decision_correction: 'bg-blue-900 text-blue-200',
  deletion_candidate:  'bg-red-900 text-red-200',
  other:               'bg-gray-700 text-gray-300',
}
```

**`SuggestedChangeView({ flag, gameId })` component** — replaces helper function so `useQuery` usage stays Hook-rule compliant. Switches on `flag.flag_type`:

| `flag_type` | Rendered diff |
|---|---|
| `entity_duplicate` | Fetches both entity names via two parallel `useQuery` calls using `getEntity(id)`. Display as: `'Merge "[duplicate name]" (id: {duplicateId}) into "[canonical name]" (id: {canonicalId})'`. While loading: show `'Merge entity #{duplicateId} into entity #{canonicalId}'` as fallback. |
| `missing_entity` | Show preview as `'{entity_type}: [name]'` + first 100 chars of description with a 'Show more' toggle. |
| `missing_event` | Show first 100 chars of event text with a 'Show more' toggle. |
| `missing_decision` | Show `'{made_by}: [first 100 chars of decision text]'` with a 'Show more' toggle. |
| `missing_loot` | Show `'{item_name} → {acquired_by}'`. |
| `loot_correction` | `"acquired_by: {old} → {new_acquired_by}"` (show `loot_id` if old name unavailable) |
| `decision_correction` | `"made_by: {old} → {new_made_by}"` (show `decision_id` if old name unavailable) |
| `deletion_candidate` | `"🗑 Delete {table} row #{record_id}"` |
| `other` | `suggested_change.proposed_action` text |

> **Note:** For all other `missing_*` types not listed above, show the `suggested_change` JSON fields with the same first-100-chars truncation pattern. The 'Show more' toggle can live inside `SuggestedChangeView` (or an extracted `<Expandable>` inline component).

**Optimistic UI + Undo:**

```typescript
const [optimisticStatus, setOptimisticStatus] = useState<FlagStatus | null>(null);
const displayStatus = optimisticStatus ?? flag.status;
```

- **Apply**: `setOptimisticStatus('applied')` immediately → fire `applyAuditFlag(flag.game_id, flag.id)` mutation → on success invalidate query keys (see below) + show undo toast. On error: `setOptimisticStatus(null)` + show error state on card.
- **Dismiss**: same pattern with `setOptimisticStatus('dismissed')` → `dismissAuditFlag(flag.game_id, flag.id)`.
- **Undo toast**: show for 5 seconds. If the user clicks Undo within 5s, call `reopenAuditFlag(gameId, flagId)` → `POST .../reopen`. Invalidate `['audit-flags', gameId]` on either path (whether the mutation completes normally or undo is clicked and reopen fires). A minimal `Toast` component is created at `frontend/src/components/Toast.tsx`. It accepts `message`, `duration` (default 5000ms), and an optional `onUndo` callback. Renders a fixed-position overlay. No external library needed.
- **Undo toast**: show for 5 seconds. If the user clicks Undo within 5s, call `reopenAuditFlag(gameId, flagId)` → `POST .../reopen`. Invalidate `['audit-flags', gameId]` on either path (whether the mutation completes normally or undo is clicked and reopen fires). A minimal `Toast` component is created at `frontend/src/components/Toast.tsx`. It accepts `message`, `duration` (default 5000ms), and an optional `onUndo` callback. Renders a fixed-position overlay. No external library needed. When mutation response includes `message`, display that server-provided text.
- When `displayStatus !== 'pending'`: render `[Applied ✓]` or `[Dismissed]` label in place of the action buttons.

**Query cache invalidation in `applyAuditFlag` `onSuccess`:**

| `flag_type` | Invalidate |
|---|---|
| `entity_duplicate` | `['entities', gameId]` |
| `missing_entity` | `['entities', gameId]` |
| `missing_event` | `['events', gameId]` |
| `loot_correction` | `['loot', gameId]` |
| `decision_correction` | `['decisions', gameId]` |
| `missing_decision` | `['decisions', gameId]` |
| `missing_loot` | `['loot', gameId]` |
| `deletion_candidate` | infer from `suggested_change.table`: `'entities'` → `['entities', gameId]`; `'loot'` → `['loot', gameId]`; `'events'` → `['events', gameId]`; `'decisions'` → `['decisions', gameId]`; `'important_quotes'` → `['quotes', gameId]`; `'quests'` → `['quests', gameId]`; `'threads'` → `['threads', gameId]` |
| `other` | no invalidation |

All flag operations (apply and dismiss) also invalidate `['audit-flags', gameId]` to refresh the flags list and the pending badge count in `GameDetail`.

---

### `NotesTab.tsx` changes

In `NoteCard`, check `note.is_audit`. If `true`:

- **Badge**: render a `bg-orange-900 text-orange-300` badge with text `"Audit Correction"` next to (or instead of) the character name badge.
- **Summary text**: use `text-gray-400` instead of the default `text-gray-100` (muted appearance).
- **Delete button**: hide entirely — audit notes should not be manually deleted.
- **Expand/collapse and is_audit treatment**: When an `is_audit` NoteCard is expanded, show a custom 'Audit Changes' section instead of the standard linked-data breakdown. The audit note's linked data (entities, events, decisions, loot, etc. via the existing note join queries) shows what was created or bulk-corrected in that run. Add a header **'Corrected by Foundry Bridge Auditor'** to distinguish it from session note expansions.
  - **Implementation:** The existing expand queries (`getNoteEvents`, `getNoteLoot`, etc.) work unchanged since the synthetic note is a real `Note` row with the same join tables. No new queries needed. Just change the section header text and card style when `note.is_audit === true`.

---

## Relevant Files

| File | Change |
|------|--------|
| `src/foundry_bridge/models.py` | Add `AuditRun`, `AuditFlag` ORM models; add `is_audit` boolean to existing `Note` model |
| `src/foundry_bridge/db.py` | Add all audit read/write DB functions |
| `src/foundry_bridge/note_taker.py` | Add `check_and_trigger_audit()` call after note write; import `_game_locks` from `locks.py` (removing own dict) |
| `src/foundry_bridge/locks.py` | **NEW** — shared per-game asyncio lock registry |
| `src/foundry_bridge/note_generator.py` | Reference pattern (no changes) |
| `src/foundry_bridge/audit_generator.py` | **NEW** — LangGraph audit agent |
| `src/foundry_bridge/auditor.py` | **NEW** — background audit pipeline |
| `src/foundry_bridge/server.py` | Add `reset_stale_audit_runs()` call to FastAPI lifespan startup hook (before polling loop) |
| `src/foundry_bridge/api.py` | Add audit run/flag/restore endpoints + GET entity endpoint + Pydantic schemas; add 409 guard to `DELETE /notes/{id}` |
| `alembic/versions/0010_add_audit_tables.py` | **NEW** — DB migration |
| `frontend/src/types.ts` | Add `AuditRun`, `AuditFlag`, `FlagType`, `FlagStatus`; add `is_audit` to `Note` |
| `frontend/src/api.ts` | Add `getAuditRuns`, `triggerAudit`, `getAuditFlags`, `applyAuditFlag`, `dismissAuditFlag`, `reopenAuditFlag`, `getEntity` |
| `frontend/src/pages/GameDetail.tsx` | Add Audit tab + route + pending-flag badge |
| `frontend/src/pages/tabs/AuditTab.tsx` | **NEW** — `AuditTab`, `AuditRunHeader`, `AuditFlagList`, `FlagCard` components |
| `frontend/src/pages/tabs/NotesTab.tsx` | Add `is_audit` visual treatment to `NoteCard` |

---

## Decisions

- **Transcript window:** pulled via `source_transcript_ids` from notes created since last audit — no schema change to `Transcript` needed
- **Entity merges:** flagged as low-confidence for human review; `apply_audit_flag` performs a full atomic merge (FK reassignment + deletion) for `entity_duplicate` flags
- **Context window overflow:** The audit agent accepts `GraphRecursionError` as the failure fallback for context overflow scenarios. No token guardrail is applied. The `AUDIT_AFTER_N_NOTES` threshold naturally bounds window size for ongoing campaigns; only the very first audit on a long campaign risks overflow (accepted risk).
- **Per-game lock:** defined in `locks.py` and imported by both `note_taker.py` and `auditor.py`; audit skips if lock is held
- **Audit run heartbeat + stale reset:** runs update `heartbeat_at`, and stale-running rows (>15 minutes old) are failed at startup and by periodic 5-minute sweeper.
- **`resolved_by_note_id` on threads:** set to the synthetic `audit_note_id` when resolved by auditor; `resolved_at` is set to now
- **`suggested_change` JSONB:** free-form dict keyed by what the `apply_audit_flag` dispatcher reads; each `flag_type` has a documented shape
- **Failed audits:** `get_last_audit_run_for_game` ignores non-completed runs. A failed audit does not reset the unaudited note window — the next note pipeline completion will re-trigger the audit.
- **Run creation timing:** `AuditRun` is pre-created at trigger time (`trigger_source=auto|manual`), then `audit_note_id` is set after synthetic note creation in the write path.
- **Early-failure cleanup:** if failure occurs before synthetic note creation completes, delete pre-created run row and emit structured log.
- **Synthetic note ordering:** Synthetic note is created before linking `audit_note_id` onto the pre-created run; if Step 2+ fails, that synthetic note is deleted.
- **Post-commit embedding failure policy:** keep committed audit writes and retry embeddings in background with bounded exponential backoff (`5s`, `15s`, `45s`, max 3 attempts), then log and stop.
- **Soft-delete policy for `deletion_candidate`:** quests and threads are soft-deleted (`is_deleted`, `deleted_at`, `deleted_reason`) and can be restored via API.
- **Flag transition semantics:** apply/dismiss/reopen are idempotent; no-op transitions return normal success with `noop=true` metadata.
- **Reason-code contract:** wrapper responses include machine-readable `reason_code` values; baseline set: `conflict_running`, `noop_no_new_notes`, `schedule_failed`, `precreate_failed`, `early_pipeline_failure`.
- **Reason-code transport:** reason codes are present in wrapper bodies and mirrored via `X-Reason-Code` header on relevant conflict/error responses.
- **Observability correlation:** use structured logs with per-run correlation IDs for cross-process tracing; correlation ID is log metadata only (no schema column).
- **`is_audit` filtering:** `GET /notes` returns all notes including audit notes. No server-side filter. Frontend is responsible for visual distinction using `is_audit`.
- **Frontend audit UI:** Implemented in Phase 7. `AuditTab` owns data fetching; `GameDetail` fetches the pending flag count for the nav badge and uses capped `50+` display behavior. Optimistic UI with undo toast for apply/dismiss actions.

---

## Verification Checklist

- [ ] `alembic upgrade head` — migration applies cleanly, both tables created
- [ ] Process N note runs via seed data (`01` + `01b` + `01c` + `01d` + `01e`) → `audit_runs` row created with `status=completed`
- [ ] `audit_flags` table populated with low-confidence findings
- [ ] `GET /api/games/{id}/audit-flags` returns expected flags
- [ ] `POST /api/games/{id}/audit-flags/{flag_id}/apply` updates target record in DB
- [ ] Audit-updated entity descriptions visible in `entities` table
- [ ] Old quest descriptions archived in `quest_description_history` after audit update
- [ ] Per-game lock correctly prevents concurrent note + audit run
- [ ] `AUDIT_AFTER_N_NOTES` env var respected

> **Testing scope note:** First implementation pass uses manual verification only; automated tests are deferred to a follow-up pass.

---

This document is the canonical specification; all design-review decisions are already integrated above.

---

## Duck Review Cycle 2

### Round 1 — Current Code vs Plan (March 2026)

#### Decisions Captured

- Rollout order: schema/migration first, then backend, then API, then frontend.
- Migration strategy: keep a single `0010` migration file.
- Soft-delete defaults: existing rows start as `is_deleted=false`, `deleted_at=NULL`, `deleted_reason=NULL`.
- Heartbeat cadence: update by major pipeline phase.
- Sweeper deployment: run in every process with idempotent SQL.
- Synthetic note cleanup: immediate best-effort delete in Step 2+ exception path.
- Idempotent mutation responses: use explicit wrapper with `noop` + `message` metadata.
- Restore endpoints: no additional authorization guard in v1.
- Reopen compatibility: remove legacy `409` expectation from frontend behavior.
- `50+` semantics: treat as page-cap indicator, not exact total.
- Lock refactor sequencing: move `note_taker` lock state to shared `locks.py` before `auditor.py`.
- Search policy: exclude soft-deleted quests/threads by default.
- Frontend hook safety: keep suggested-change rendering in a dedicated component.
- Initial testing scope: manual verification only.

#### Plan Updates Applied

- Added `AuditFlagMutationOut` and updated audit-flag mutation route response contracts.
- Added `AuditFlagMutation` frontend type and updated `api.ts` mutation function signatures.
- Added explicit lock-rollout note under Phase 4 hook integration.
- Added initial testing-scope note to verification section.

#### Research Files Reviewed

- [plan-auditingAgent.prompt.md](plan-auditingAgent.prompt.md)
- [src/foundry_bridge/models.py](src/foundry_bridge/models.py)
- [src/foundry_bridge/db.py](src/foundry_bridge/db.py)
- [src/foundry_bridge/api.py](src/foundry_bridge/api.py)
- [src/foundry_bridge/note_taker.py](src/foundry_bridge/note_taker.py)
- [src/foundry_bridge/server.py](src/foundry_bridge/server.py)
- [frontend/src/types.ts](frontend/src/types.ts)
- [frontend/src/api.ts](frontend/src/api.ts)
- [frontend/src/pages/GameDetail.tsx](frontend/src/pages/GameDetail.tsx)

#### Open Questions

1. Resolved in Round 2.

### Round 2 — Contract Resolution (March 2026)

#### Decisions Captured

- Mutation wrapper scope: always return `AuditFlagMutationOut` for apply/dismiss/reopen.
- Heartbeat policy: add fallback heartbeat tick every 60 seconds during long operations.
- Trigger semantics: create running `AuditRun` immediately in trigger endpoint and return full row with `id`.
- Sweeper placement: run periodic stale-run sweeper in all long-running processes (API + WS).
- Frontend toasts: prefer server-provided mutation `message` when present.
- `50+` behavior: keep `50+` permanently (do not switch to exact loaded count).
- Manual verification dataset: require full seed chain (`01`, `01b`, `01c`, `01d`, `01e`).
- Trigger conflicts: keep query check + lock check + DB unique-index conflict handling.
- Wrapper field naming: keep `flag` as payload key.

#### Plan Updates Applied

- Updated trigger endpoint contract to immediate `AuditRun` creation and full-row response.
- Updated mutation route contracts to always use `AuditFlagMutationOut`.
- Added explicit heartbeat fallback note (60s).
- Added server-message toast behavior note for frontend.
- Updated verification checklist with required full seed-chain manual test.

#### Open Questions

1. Resolved in Round 3.

### Round 3 — Pipeline Binding & Trigger Semantics (March 2026)

#### Decisions Captured

- Pre-create running `AuditRun` in both manual and auto trigger paths.
- Pass `audit_run_id` explicitly through `_run_audit_pipeline` and audit DB write path.
- On early failure before synthetic note exists, mark pre-created run failed and keep `audit_note_id=NULL`.
- Idempotent `noop=true` semantics apply to apply, dismiss, and reopen when state already matches.
- Enable sweeper startup jitter (`0-30s`) and skip held in-process locks.
- Manual trigger supports `force=true` even when unaudited note count is zero.
- Persist trigger source (`auto`/`manual`) on each `AuditRun`.
- Trigger endpoint returns wrapper payload with `run` + metadata.
- No mandatory PR evidence gate for manual-first verification.

#### Plan Updates Applied

- Added `trigger_source` to schema and API/frontend output contracts.
- Updated trigger route to wrapper response + `force` query param.
- Updated auto-trigger hook and pipeline signature to pass pre-created `audit_run_id`.
- Expanded idempotent behavior documentation for all flag mutation endpoints.
- Added sweeper jitter + lock-skip runtime behavior notes.

#### Open Questions

1. None currently blocking implementation.

## Duck Review Cycle 3

### Round 1 — Trigger Flow and Runtime Semantics (March 2026)

#### Decisions Captured

- Use a shared helper to pre-create runs for both auto and manual paths.
- Trigger wrapper `noop=true` is used for accepted no-work cases.
- Manual non-force trigger with zero unaudited notes returns `200` with `noop=true` + message.
- Auto-trigger path skips when threshold not met (no noop run row).
- Heartbeat timer ownership stays in `auditor.py` runtime logic.
- Trigger source validation should exist in both app layer and DB constraints.
- Sweeper lock-skip behavior retries on next cycle and relies on heartbeat freshness.
- Jitter scope is startup-only (`0-30s`) for periodic sweepers.
- Mutation wrappers always include `message` field (nullable).
- Add a pre-implementation consistency checklist section to reduce plan drift.
- Keep default frontend tab redirect to quests.

#### Plan Updates Applied

- Added this review round to plan history with resolved choices and follow-up items.
- Flagged early-failure run handling as conflicting with prior cycle decision for explicit resolution in Round 2.

#### Research Files Reviewed

- [plan-auditingAgent.prompt.md](plan-auditingAgent.prompt.md)
- [src/foundry_bridge/api.py](src/foundry_bridge/api.py)
- [src/foundry_bridge/db.py](src/foundry_bridge/db.py)
- [src/foundry_bridge/note_taker.py](src/foundry_bridge/note_taker.py)
- [frontend/src/api.ts](frontend/src/api.ts)

#### Open Questions

1. Resolved in Round 2.

### Round 2 — Trigger Wrapper and Failure Policy (March 2026)

#### Decisions Captured

- Early failure before synthetic-note creation deletes pre-created run row.
- `AuditRunTriggerOut.run` is nullable; noop responses may return `run=null`.
- Shared precreate helper does not enforce thresholds; caller owns threshold decisions.
- Manual non-force + zero notes path skips helper and returns noop wrapper directly.
- Keep `409` for active-run conflicts.
- Define canonical message constants for noop/conflict text.
- Auto path pre-creates run immediately after threshold check and before task scheduling.
- Early-failure delete path emits structured log event.
- Consistency checklist remains in Duck review notes (no standalone canonical section).

#### Plan Updates Applied

- Updated canonical sections for nullable trigger wrapper run field and noop behavior.
- Updated early-failure behavior from failed-row retention to delete-row cleanup.
- Added caller-vs-helper threshold responsibility note.
- Added explicit noop response contract for non-force zero-note trigger.

#### Open Questions

1. Should trigger wrapper use a stable machine code field (for example `reason_code`) in addition to `message` to avoid frontend string matching?
2. For deleted pre-created runs on early failure, should we log the deleted run id only, or also a synthetic correlation id for cross-process tracing?
3. Should auto-trigger precreate and task launch happen in one DB transaction + immediate task schedule block, or best-effort sequential steps?

### Round 3 — Response Codes and Observability (March 2026)

#### Decisions Captured

- Add `reason_code` field to both trigger and mutation wrappers.
- Use wrapper-level `reason_code` (alongside `message`) as primary frontend branching signal.
- Include correlation ID in structured logs for cross-process tracing.
- Keep correlation ID as log-only metadata (no DB schema change).
- Keep precreate + scheduling as best-effort sequential operations with compensating cleanup.
- If scheduling fails after precreate, delete pre-created run and emit `schedule_failed` reason code.
- Keep canonical reason-code baseline: `conflict_running`, `noop_no_new_notes`, `schedule_failed`, `precreate_failed`, `early_pipeline_failure`.
- Drop checklist requirement entirely (not canonical, not Duck-only).

#### Research Findings Incorporated

- Existing API patterns are direct-model responses with `HTTPException` string details and no wrapper standardization.
- Existing logging is structured but inconsistent for cross-cutting correlation fields.
- Existing background task behavior relies on best-effort scheduling and exception logging.

#### Research Files Reviewed

- [src/foundry_bridge/api.py](src/foundry_bridge/api.py)
- [src/foundry_bridge/server.py](src/foundry_bridge/server.py)
- [src/foundry_bridge/note_taker.py](src/foundry_bridge/note_taker.py)
- [src/foundry_bridge/db.py](src/foundry_bridge/db.py)
- [frontend/src/api.ts](frontend/src/api.ts)
- [plan-auditingAgent.prompt.md](plan-auditingAgent.prompt.md)

#### Plan Updates Applied

- Added `reason_code` to wrapper schema/type contracts.
- Added reason-code enum baseline to decisions section.
- Added structured correlation logging decision with no schema changes.

#### Open Questions

1. Resolved in Round 4.

### Round 4 — Reason-Code Transport Finalization (March 2026)

#### Decisions Captured

- Frontend uses strict `ReasonCode` TypeScript union now.
- Mirror reason codes in response header `X-Reason-Code` on relevant non-wrapper conflicts/errors.
- Keep standard HTTP error body detail text for `409` while adding header reason code.
- Close Cycle 3 as complete.

#### Plan Updates Applied

- Added `ReasonCode` union type to frontend type contract examples.
- Updated wrapper types to use `ReasonCode | null`.
- Added API contract note for `X-Reason-Code` on conflict/error responses.

#### Open Questions

1. None currently blocking implementation.
