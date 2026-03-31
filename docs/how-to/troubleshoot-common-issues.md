# How to Troubleshoot Common Issues

This guide shows you how to diagnose and fix common local and Docker deployment problems.

## Prerequisites

- Access to service logs (`docker compose logs` or local console output)
- Access to API and health endpoints

## Problem: Health endpoint is unavailable

Run:

```bash
curl http://localhost:8766/health
```

If it fails:

1. Confirm bridge service is running.
1. Check bridge logs:

```bash
docker compose logs bridge --tail=200
```

1. Confirm port `8766` is not blocked by another process.

## Problem: `DEEPGRAM_API_KEY is not set`

1. Add `DEEPGRAM_API_KEY` to `.env`.
1. Restart bridge service:

```bash
docker compose restart bridge
```

## Problem: Model provider key mismatch

If startup reports missing key for selected provider:

1. Check `MODEL_PROVIDER` in `.env`.
1. Provide matching key:

- `MODEL_PROVIDER=openai` requires `OPENAI_API_KEY`
- `MODEL_PROVIDER=anthropic` requires `ANTHROPIC_API_KEY`

1. Restart service after updates.

## Problem: Frontend cannot reach API

1. Verify API is reachable:

```bash
curl http://localhost:8767/api/games
```

1. If running Vite dev server, confirm proxy target in `frontend/vite.config.ts` points to `http://localhost:8767`.

1. Restart frontend dev server.

## Problem: No transcripts are being created

1. Verify userscript is enabled in Foundry browser.
1. Confirm `CONFIG.WS_URL` in `userscript.js` points to reachable bridge host.
1. Watch userscript console logs (`[FoundryAudioBridge]` / `[FAB]`).
1. Verify bridge WebSocket port `8765` is reachable from the Foundry browser host.

## Problem: Audit run cannot start due to conflict

If trigger returns `conflict_running`:

1. Check running audits:

```bash
curl "http://localhost:8767/api/games/1/audit-runs"
```

1. Wait for current run completion or retry later.

## Related

- [How to deploy with Docker Compose](./deploy-docker-compose.md)
- [How to integrate Foundry VTT userscript](./foundry-integration.md)
- [How to run local development](./local-development.md)
