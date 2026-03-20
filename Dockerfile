FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the official `uv` binaries from Astral's image (pin as desired)
# (the uv image places the binaries in `/usr/local/bin`)
COPY --from=ghcr.io/astral-sh/uv:python3.11-trixie-slim /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

# Install project dependencies using `uv`
COPY pyproject.toml /app/
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=never
RUN uv sync --python /usr/local/bin/python3.11

# Copy project files
COPY . /app

EXPOSE 8765

CMD ["/app/.venv/bin/python", "main.py"]
