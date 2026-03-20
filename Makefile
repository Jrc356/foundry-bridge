.PHONY: sync sync-transcriber run run-transcriber build up up-bridge down

# ── Local dev ────────────────────────────────────────────────────────────────

sync:
	uv sync

sync-transcriber:
	uv sync --extra transcriber

run:
	uv run foundry-bridge

run-transcriber:
	uv run foundry-bridge-transcriber

# ── Docker ───────────────────────────────────────────────────────────────────

build:
	docker compose build

up:
	docker compose up

up-bridge:
	docker compose up bridge

down:
	docker compose down
