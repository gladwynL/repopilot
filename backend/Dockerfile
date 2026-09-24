# syntax=docker/dockerfile:1
# RepoPilot API: production image. Build context is backend/.

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
# Runtime dependencies only; requirements-dev.txt (pytest, ruff) never enters the image.
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt


FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    # Only trust X-Forwarded-* from this address range (the reverse proxy's network).
    # Override per deployment; the default trusts nothing but loopback.
    FORWARDED_ALLOW_IPS=127.0.0.1

RUN groupadd --system --gid 10001 repopilot \
    && useradd --system --uid 10001 --gid repopilot --no-create-home --shell /usr/sbin/nologin repopilot

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER repopilot
EXPOSE 8000

# Liveness only: /health does not touch the database, GitHub, or OpenAI.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# One process per container: the AI-review concurrency limit is per process, and scaling is
# done by running more containers. Access logs come from the reverse proxy (which strips the
# OAuth callback's query string), so Uvicorn's own access log is off.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", \
     "--no-access-log", \
     "--no-server-header", \
     "--timeout-graceful-shutdown", "30"]
