FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies
COPY pyproject.toml /app/
RUN pip install --no-cache-dir "websockets>=16.0"

# Copy project files
COPY . /app

EXPOSE 8765

CMD ["python", "main.py"]
