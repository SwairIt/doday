# Multi-stage build: builder installs deps with uv, runtime is slim Python.
# Result: ~150 MB image, no dev deps, no cache.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv binary
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install runtime deps only (no dev group). Cache layer.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Now copy source and re-sync (project itself is package=false in pyproject)
COPY . .

# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root user — never run web server as root in prod
RUN groupadd -r doday && useradd -r -g doday -d /app -s /sbin/nologin doday

WORKDIR /app

# Bring over the venv + source from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=doday:doday /app /app

# Make entrypoint executable
RUN chmod +x /app/scripts/start.sh

USER doday

EXPOSE 9100

# Lightweight healthcheck against /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9100/health', timeout=3).status==200 else 1)" || exit 1

ENTRYPOINT ["/app/scripts/start.sh"]
