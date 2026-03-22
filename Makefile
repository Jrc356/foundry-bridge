.PHONY: sync sync-transcriber run run-transcriber run-api run-frontend build up up-bridge down

# ── Local dev ────────────────────────────────────────────────────────────────

sync:
	uv sync

sync-transcriber:
	uv sync --extra transcriber

run:
	uv run foundry-bridge

run-transcriber:
	uv run foundry-bridge-transcriber

run-api:
	uv run uvicorn foundry_bridge.api:app --reload --port 8767

run-frontend:
	cd frontend && npm run dev

# ── Docker ───────────────────────────────────────────────────────────────────

build:
	docker compose build

up:
	docker compose up

up-bridge:
	docker compose up bridge

down:
	docker compose down
