FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:python3.11-trixie-slim /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

COPY pyproject.toml /app/
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=never

# ── Bridge ────────────────────────────────────────────────────────────────────
FROM base AS bridge
RUN uv sync --python /usr/local/bin/python3.11
COPY . /app
EXPOSE 8765
CMD ["/app/.venv/bin/python", "main.py"]

# ── Transcriber ───────────────────────────────────────────────────────────────
FROM bridge AS transcriber
RUN uv sync --extra transcriber --python /usr/local/bin/python3.11
CMD ["/app/.venv/bin/python", "subscriber_transcriber.py"]
