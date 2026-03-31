# Environment Variables

Runtime configuration for Foundry Bridge.

## Core Runtime

|Name|Required|Default|Used by|Description|
|---|---|---|---|---|
|`DATABASE_URL`|Yes|None|backend|PostgreSQL connection string. `postgresql://` is converted internally to asyncpg scheme.|
|`DEEPGRAM_API_KEY`|Yes|empty|transcriber|Credentials for Deepgram realtime transcription.|
|`MODEL_PROVIDER`|Conditional|`openai`|note/audit generators|LLM provider selector. Supported values include `openai` and `anthropic`.|
|`MODEL`|No|`gpt-5.4`|note/audit generators|Model identifier passed to the LangChain agent model string.|
|`OPENAI_API_KEY`|Conditional|empty|note generator|Required when `MODEL_PROVIDER=openai`.|
|`ANTHROPIC_API_KEY`|Conditional|empty|note generator|Required when `MODEL_PROVIDER=anthropic`.|
|`EMBEDDING_MODEL`|No|`nomic-ai/nomic-embed-text-v1.5`|embedding layer|FastEmbed model name used for vector generation.|

## Pipeline Cadence and Throughput

|Name|Required|Default|Used by|Description|
|---|---|---|---|---|
|`NOTE_CADENCE_MINUTES`|No|`10` (code default)|note taker|Polling interval for unprocessed transcript batches.|
|`RECENT_NOTES_LIMIT`|No|`3`|note taker|Number of recent notes included as generation context.|
|`AUDIT_CADENCE_SECONDS`|No|`60`|auditor|Sweep cadence for stale-audit and scheduling checks.|
|`AUDIT_AFTER_N_NOTES`|No|`5`|auditor|Threshold for auto-audit scheduling after note generation.|

## Networking

|Name|Required|Default|Used by|Description|
|---|---|---|---|---|
|`WS_PORT`|No|`8765`|server|WebSocket ingestion port.|
|`HTTP_PORT`|No|`8766`|server|Health endpoint port (`/health`).|
|`API_PORT`|No|`8767`|server|FastAPI and SPA serving port.|

## Logging and Agent Debugging

|Name|Required|Default|Used by|Description|
|---|---|---|---|---|
|`LOG_LEVEL`|No|`INFO`|runtime|Root logger level.|
|`LOG_COLOR`|No|`true`|runtime|Enables ANSI-colored log formatter.|
|`AGENT_DEBUG`|No|`false`|note/audit generators|Enables verbose agent debugging when true.|

## Docker Compose-Oriented Variables

|Name|Required|Default|Used by|Description|
|---|---|---|---|---|
|`POSTGRES_PASSWORD`|Yes for compose|`foundry`|postgres/bridge/migrate|Password for the compose PostgreSQL service and dependent URLs.|
|`FASTEMBED_CACHE_PATH`|No|`/app/.cache/fastembed`|bridge container|Location of FastEmbed model cache in container runtime.|

## See also

- [CLI commands](./cli-commands.md)
- [How to set up API keys](../how-to/setup-api-keys.md)
- [How to deploy with Docker Compose](../how-to/deploy-docker-compose.md)
