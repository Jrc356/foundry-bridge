# Audit System Redesign Work Tracker

This tracker is the orchestrator source of truth for delegated implementation and delegated review.
Each chunk must complete this loop before marked done:
1. Implementation subagent
2. Review subagent
3. Fix subagent (if needed)
4. Re-review subagent (repeat until approved)

## Chunk Status

- [x] Chunk 1: DB schema and shared contract baseline
  - Scope:
    - Add migration 0011 for audit_flags redesign
    - Update AuditFlag ORM fields in models.py
    - Update API output model in api.py
    - Update frontend types baseline in frontend/src/types.ts
  - Must include:
    - Drop flag_type and target_type
    - Add operation, table_name, confidence with constraints
    - Add unsupported_operation reason code and DiffPayload type
  - Review status: Approved

- [x] Chunk 2: Audit generator schema + prompt + validation
  - Scope:
    - Replace flat output models with CRUD/table changesets
    - Rewrite SYSTEM_PROMPT for CRUD + confidence + tool rules + merge guidance
    - Replace normalize function with validate function
  - Must include:
    - Empty-update drop behavior
    - entity_type validation for creates
    - cross-create reference support (quest_name/entity_name)
  - Review status: Approved

- [x] Chunk 3: write_audit_pipeline_result redesign
  - Scope:
    - Rewrite write path to unified CRUD behavior
    - Create three-pass create ordering
    - High confidence immediate apply and flag persistence
  - Must include:
    - before/after snapshot payloads
    - create pending _after = null
    - quest/thread special handling and description history
    - merge support in write path
  - Review status: Approved

- [x] Chunk 4: _apply_flag_change + apply_audit_flag redesign
  - Scope:
    - Replace legacy flag_type dispatch with operation/table dispatch
    - Implement NamedTuple return and embedding handoff
    - Implement merge FK migration behavior per table
  - Must include:
    - unsupported_operation reason when needed
    - loot/event collision noops
    - combat_updates delete support
    - apply_audit_flag post-commit _write_flag_embeddings fire-and-forget
  - Review status: Approved

- [x] Chunk 5: Frontend DiffView and Audit tab integration
  - Scope:
    - Add DiffView component
    - Swap AuditTab JSON details with DiffView
    - Add confidence badge and new operation/table labels
  - Must include:
    - update unchanged rows: first 3 shown + collapse rest
    - stale applied update snapshot label
    - create pending/applied behavior for null _after
  - Review status: Approved

- [x] Chunk 6: End-to-end verification
  - Scope:
    - Run backend checks/tests and frontend lint/build where available
    - Sanity-check migration and type alignment
    - Confirm no leftover flag_type/target_type references
  - Review status: Approved

## Delegation Log

- Orchestrator initialized tracker and chunk plan.
- Chunk 1 implementation delegated and applied by subagent.
- Chunk 1 independent review returned changes required; fix pass delegated and applied.
- Chunk 1 re-review delegated and approved.
- Chunk 2 implementation delegated and applied by subagent.
- Chunk 2 independent review delegated and approved.
- Chunk 3 implementation delegated and applied by subagent.
- Chunk 3 independent review delegated and approved.
- Chunk 4 implementation delegated and applied by subagent.
- Chunk 4 independent review delegated and approved.
- Chunk 5 implementation delegated and applied by subagent.
- Chunk 5 independent review delegated and approved.
- Chunk 6 verification delegated and executed by subagent (checks passed).
- Chunk 6 independent final review delegated and approved.

## Approval Log

- Chunk 1 approved.
- Chunk 2 approved.
- Chunk 3 approved.
- Chunk 4 approved.
- Chunk 5 approved.
- Chunk 6 approved.
