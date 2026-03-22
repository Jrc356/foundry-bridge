FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:python3.11-trixie-slim /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

COPY pyproject.toml uv.lock /app/
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=never

# ── Frontend build ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ── Bridge ────────────────────────────────────────────────────────────────────
FROM base AS bridge
# Install dependencies only (cached layer — invalidated only when pyproject.toml/uv.lock changes)
RUN uv sync --frozen --no-install-project --python /usr/local/bin/python3.11

# Pre-download the FastEmbed model into the image (~270 MB, cached as a distinct layer)
# Do this before copying source code so changes to Python files don't invalidate this cache
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN /app/.venv/bin/python -c \
    "from fastembed import TextEmbedding; TextEmbedding(model_name='nomic-ai/nomic-embed-text-v1.5')"

COPY . /app
# Install the project itself now that source is present
RUN uv sync --frozen --python /usr/local/bin/python3.11

# Copy in the built React app
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
EXPOSE 8765 8767
CMD ["/app/.venv/bin/foundry-bridge"]

# ── Migrate ───────────────────────────────────────────────────────────────────
FROM bridge AS migrate
CMD ["/app/.venv/bin/alembic", "upgrade", "head"]
