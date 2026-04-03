# Database Schema

Primary relational schema defined in `src/foundry_bridge/models.py` and evolved through `alembic/versions/` migrations.

## Core tables

|Table|Purpose|Key fields|
|---|---|---|
|`games`|Campaign identity namespace|`id`, `hostname`, `world_id`, `name`, `created_at`|
|`transcripts`|Raw turn-level transcription records|`id`, `game_id`, `participant_id`, `character_name`, `text`, `note_taker_processed`|
|`notes`|Generated note summaries|`id`, `game_id`, `summary`, `source_transcript_ids`, `is_audit`, `embedding`|
|`entities`|Extracted world entities|`id`, `game_id`, `entity_type`, `name`, `description`, `embedding`|
|`threads`|Open/resolved narrative threads|`id`, `game_id`, `text`, `is_resolved`, `resolution`, `quest_id`, `is_deleted`|
|`quests`|Quest tracking and status|`id`, `game_id`, `name`, `description`, `status`, `quest_giver_entity_id`, `is_deleted`|

## Supporting tables

|Table|Purpose|
|---|---|
|`player_characters`|Character names excluded from generated entity output|
|`events`|Significant narrative events|
|`decisions`|Party decisions|
|`loot`|Acquired items and ownership|
|`combat_updates`|Combat encounter and outcome snapshots|
|`important_quotes`|Important quoted lines with speaker linkage|
|`quest_description_history`|Historical quest description snapshots|
|`audit_runs`|Audit execution metadata and status|
|`audit_flags`|Suggested create/update/delete/merge operations from audits|

## Join tables

|Table|Relationship|
|---|---|
|`notes_entities`|many-to-many between notes and entities|
|`notes_events`|many-to-many between notes and events|
|`notes_loot`|many-to-many between notes and loot|

## Key constraints and conventions

|Area|Constraint / rule|
|---|---|
|Game identity|Unique key on `(hostname, world_id)` for `games`|
|Embeddings|Vector columns use pgvector with dimension 768 (`VECTOR_DIM`)|
|Quest status|`quests.status` constrained to active/completed semantics in API layer|
|Audit operation|`audit_flags.operation` constrained to `create`, `update`, `delete`, `merge`|
|Audit table name|`audit_flags.table_name` constrained to allowed table taxonomy|
|Audit confidence|`audit_flags.confidence` constrained to `low`, `medium`, `high`|
|Soft deletes|Quests and threads use logical deletion fields (`is_deleted`, `deleted_at`, `deleted_reason`)|

## Migration lineage

Current migration chain includes revisions `0001` through `0011`, covering:

- Initial transcript schema
- Quest model and history tables
- Note-entity relationship tables
- Audit runs and audit flags
- Audit taxonomy redesign (`0011`)

## See also

- [API reference](./api.md)
- [WebSocket protocol](./websocket-protocol.md)
- [How to run database migrations](../how-to/database-migrations.md)
