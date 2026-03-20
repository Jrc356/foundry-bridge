# Database schema

foundry-bridge uses a single PostgreSQL table, `transcripts`, to store speech-to-text results produced by the transcriber subscriber.

The schema is managed with [Alembic](https://alembic.sqlalchemy.org/). Run `alembic upgrade head` to apply all migrations before starting the transcriber.

## transcripts

Stores one row per recognised speech turn for each participant.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT` | No | auto-increment | Primary key |
| `participant_id` | `VARCHAR(255)` | No | — | Foundry VTT user ID of the participant who spoke |
| `character_name` | `VARCHAR(255)` | No | — | Display name of the participant at the time of capture |
| `turn_index` | `INTEGER` | No | — | Sequential turn number within the session for this participant |
| `transcript` | `TEXT` | No | — | Recognised speech text returned by Deepgram |
| `audio_window_start` | `FLOAT` | No | — | Start time (seconds) of the audio segment within the stream |
| `audio_window_end` | `FLOAT` | No | — | End time (seconds) of the audio segment within the stream |
| `end_of_turn_confidence` | `FLOAT` | No | — | Deepgram's confidence score (0–1) that this is a complete turn |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | UTC timestamp when the row was inserted |

## Migration history

| Revision | Description |
|---|---|
| `0001_create_transcripts` | Creates the initial `transcripts` table |
| `0002_rename_label_to_character_name` | Renames the `label` column to `character_name` |

## See also

- [How to set up live transcription with Deepgram](../how-to/set-up-transcription.md) — querying this table after capture
- [Configuration reference](./configuration.md) — `DATABASE_URL` environment variable
