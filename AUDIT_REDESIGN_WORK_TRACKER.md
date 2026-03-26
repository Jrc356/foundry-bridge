# Audit System Redesign Work Tracker

This tracker is the orchestrator source of truth for delegated implementation and delegated review.
Each chunk must complete this loop before marked done:
1. Implementation subagent
2. Review subagent
3. Fix subagent (if needed)
4. Re-review subagent (repeat until approved)

## Chunk Status

- [ ] Chunk 1: DB schema and shared contract baseline
  - Scope:
    - Add migration 0011 for audit_flags redesign
    - Update AuditFlag ORM fields in models.py
    - Update API output model in api.py
    - Update frontend types baseline in frontend/src/types.ts
  - Must include:
    - Drop flag_type and target_type
    - Add operation, table_name, confidence with constraints
    - Add unsupported_operation reason code and DiffPayload type
  - Review status: Pending

- [ ] Chunk 2: Audit generator schema + prompt + validation
  - Scope:
    - Replace flat output models with CRUD/table changesets
    - Rewrite SYSTEM_PROMPT for CRUD + confidence + tool rules + merge guidance
    - Replace normalize function with validate function
  - Must include:
    - Empty-update drop behavior
    - entity_type validation for creates
    - cross-create reference support (quest_name/entity_name)
  - Review status: Pending

- [ ] Chunk 3: write_audit_pipeline_result redesign
  - Scope:
    - Rewrite write path to unified CRUD behavior
    - Create three-pass create ordering
    - High confidence immediate apply and flag persistence
  - Must include:
    - before/after snapshot payloads
    - create pending _after = null
    - quest/thread special handling and description history
    - merge support in write path
  - Review status: Pending

- [ ] Chunk 4: _apply_flag_change + apply_audit_flag redesign
  - Scope:
    - Replace legacy flag_type dispatch with operation/table dispatch
    - Implement NamedTuple return and embedding handoff
    - Implement merge FK migration behavior per table
  - Must include:
    - unsupported_operation reason when needed
    - loot/event collision noops
    - combat_updates delete support
    - apply_audit_flag post-commit _write_flag_embeddings fire-and-forget
  - Review status: Pending

- [ ] Chunk 5: Frontend DiffView and Audit tab integration
  - Scope:
    - Add DiffView component
    - Swap AuditTab JSON details with DiffView
    - Add confidence badge and new operation/table labels
  - Must include:
    - update unchanged rows: first 3 shown + collapse rest
    - stale applied update snapshot label
    - create pending/applied behavior for null _after
  - Review status: Pending

- [ ] Chunk 6: End-to-end verification
  - Scope:
    - Run backend checks/tests and frontend lint/build where available
    - Sanity-check migration and type alignment
    - Confirm no leftover flag_type/target_type references
  - Review status: Pending

## Delegation Log

- Orchestrator initialized tracker and chunk plan.

## Approval Log

- None yet.
