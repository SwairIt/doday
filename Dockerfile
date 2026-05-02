### Stage 1: builder — install runtime deps into a venv via uv
FROM ghcr.io/astral-sh/uv:0.11.3-python3.12-bookworm-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Lock + project files first so deps install layer caches independently of code changes.
COPY pyproject.toml uv.lock ./

# Production deps only (--no-dev skips ruff/mypy/pytest).
RUN uv sync --frozen --no-dev --no-install-project

### Stage 2: runtime — minimal slim image with the venv copied in
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Pull in the prebuilt venv.
COPY --from=builder /opt/venv /opt/venv

# Application code.
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./

# Drop privileges.
RUN useradd --create-home --uid 1000 schooltodo \
    && chown -R schooltodo:schooltodo /app
USER schooltodo

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
