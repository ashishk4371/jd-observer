FROM python:3.13-slim

# Native deps: PyMuPDF and onnxruntime (via fastembed) both need a few shared libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
COPY run_server.py ./
RUN uv sync --frozen --no-dev

# Runs as a non-root user; /data is the mounted volume for the SQLite DB + embedding cache.
RUN useradd --create-home --uid 1000 appuser && mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser

ENV JD_GLANCE_DATA_DIR=/data \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "jd_glance.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
