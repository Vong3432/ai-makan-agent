# syntax=docker/dockerfile:1

# ---------- base: Python + uv ----------
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---------- dev: all deps incl. dev, source mounted by compose, hot reload ----------
FROM base AS dev
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
EXPOSE 8000
CMD ["uvicorn", "makan.server:create_http_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]

# ---------- builder: runtime deps only ----------
FROM base AS builder
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------- prod: slim, non-root (Cloud Run) ----------
FROM python:3.12-slim AS prod
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
COPY --from=builder /opt/venv /opt/venv
USER app
# Cloud Run injects PORT; Settings.port reads it.
CMD ["makan"]
