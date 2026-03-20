FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:python3.11-trixie-slim /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

COPY pyproject.toml uv.lock /app/
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=never

# ── Bridge ────────────────────────────────────────────────────────────────────
FROM base AS bridge
# Install dependencies only (cached layer — invalidated only when pyproject.toml/uv.lock changes)
RUN uv sync --frozen --no-install-project --python /usr/local/bin/python3.11
COPY . /app
# Install the project itself now that source is present
RUN uv sync --frozen --python /usr/local/bin/python3.11
EXPOSE 8765
CMD ["/app/.venv/bin/foundry-bridge"]

# ── Transcriber ───────────────────────────────────────────────────────────────
FROM bridge AS transcriber
RUN uv sync --frozen --extra transcriber --python /usr/local/bin/python3.11
CMD ["/app/.venv/bin/foundry-bridge-transcriber"]
