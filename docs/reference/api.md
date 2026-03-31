# API Reference

REST API surface exposed by Foundry Bridge.

## Generated API schema

The authoritative API schema is served by FastAPI at runtime.

|Artifact|URL|
|---|---|
|Swagger UI|`http://localhost:8767/docs`|
|ReDoc|`http://localhost:8767/redoc`|
|OpenAPI JSON|`http://localhost:8767/openapi.json`|

## Base path

|Item|Value|
|---|---|
|API base|`/api`|
|Content type|`application/json`|

## Resource groups

### Games

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games`|List games|
|`POST`|`/api/games`|Create game|
|`GET`|`/api/games/{game_id}`|Get game|
|`PATCH`|`/api/games/{game_id}`|Update game|
|`DELETE`|`/api/games/{game_id}`|Delete game|

### Notes

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/notes`|List notes|
|`DELETE`|`/api/notes/{note_id}`|Delete note (non-audit only)|
|`GET`|`/api/games/{game_id}/notes/{note_id}/events`|List events linked to note|
|`GET`|`/api/games/{game_id}/notes/{note_id}/loot`|List loot linked to note|

### Audits

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/audit-runs`|List audit runs|
|`POST`|`/api/games/{game_id}/audit-runs/trigger`|Trigger manual audit (`force` query param supported)|
|`GET`|`/api/games/{game_id}/audit-flags`|List audit flags (`status`, `offset`, `limit`)|
|`POST`|`/api/games/{game_id}/audit-flags/{flag_id}/apply`|Apply audit flag|
|`POST`|`/api/games/{game_id}/audit-flags/{flag_id}/dismiss`|Dismiss audit flag|
|`POST`|`/api/games/{game_id}/audit-flags/{flag_id}/reopen`|Reopen audit flag|
|`POST`|`/api/games/{game_id}/quests/{quest_id}/restore`|Restore soft-deleted quest|
|`POST`|`/api/games/{game_id}/threads/{thread_id}/restore`|Restore soft-deleted thread|

### Entities

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/entities`|List entities (`entity_type` query param supported)|
|`POST`|`/api/games/{game_id}/entities`|Create entity|
|`GET`|`/api/entities/{entity_id}`|Get entity|
|`PUT`|`/api/entities/{entity_id}`|Update entity|
|`DELETE`|`/api/entities/{entity_id}`|Delete entity|

### Threads

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/threads`|List threads (`resolved` query param supported)|
|`POST`|`/api/games/{game_id}/threads`|Create thread|
|`PUT`|`/api/threads/{thread_id}`|Update thread|
|`DELETE`|`/api/threads/{thread_id}`|Delete thread|

### Transcripts

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/transcripts`|List transcripts (`character_name`, `limit`, `offset`)|
|`DELETE`|`/api/transcripts/{transcript_id}`|Delete transcript|

### Loot

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/loot`|List loot|
|`POST`|`/api/games/{game_id}/loot`|Create loot|
|`PATCH`|`/api/loot/{loot_id}`|Update loot|
|`DELETE`|`/api/loot/{loot_id}`|Delete loot|

### Quests

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/quests`|List quests (`status` query param supported)|
|`POST`|`/api/games/{game_id}/quests`|Create quest|
|`PATCH`|`/api/quests/{quest_id}`|Update quest|
|`DELETE`|`/api/quests/{quest_id}`|Delete quest|
|`GET`|`/api/quests/{quest_id}/history`|List quest description history|

### Decisions

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/decisions`|List decisions|
|`POST`|`/api/games/{game_id}/decisions`|Create decision|
|`DELETE`|`/api/decisions/{decision_id}`|Delete decision|

### Events

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/events`|List events|
|`POST`|`/api/games/{game_id}/events`|Create event|
|`DELETE`|`/api/events/{event_id}`|Delete event|

### Combat and quotes

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/combat`|List combat updates|
|`DELETE`|`/api/combat/{combat_id}`|Delete combat update|
|`GET`|`/api/games/{game_id}/quotes`|List important quotes|
|`DELETE`|`/api/quotes/{quote_id}`|Delete quote|

### Player characters

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/player_characters`|List game player characters|

### Search

|Method|Path|Description|
|---|---|---|
|`GET`|`/api/games/{game_id}/search`|Semantic search across content types (`q`, `content_type`, `limit`)|

## Audit reason-code headers

Some mutation responses include `X-Reason-Code` for machine-readable failure/no-op state.

Observed reason-code families include:

- `conflict_running`
- `noop_no_new_notes`
- `invalid_transition`
- `not_found`
- `schedule_failed`

## See also

- [Database schema](./database-schema.md)
- [How to run the audit workflow](../how-to/audit-workflow.md)
- [How to troubleshoot common issues](../how-to/troubleshoot-common-issues.md)
