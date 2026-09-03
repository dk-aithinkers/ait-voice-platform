# The service image. One image, two entrypoints: the JSON API today, and the
# voice service once it has an HTTP webhook (see docs/deploying.md).
#
# Multi-stage so the runtime carries no build tooling, no uv, and no lockfile
# — a smaller attack surface on a container that will hold PHI in memory.

# ---- build ----------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, in their own layer: they change far less often than the
# source, so a code edit does not re-resolve the world.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev \
        --extra api --extra postgres --extra aws \
        --extra anthropic --extra deepgram --extra elevenlabs --extra twilio

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev \
        --extra api --extra postgres --extra aws \
        --extra anthropic --extra deepgram --extra elevenlabs --extra twilio

# ---- runtime ---------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Non-root, and owning nothing it does not need to. A process that cannot write
# to its own code directory cannot be made to persist anything there.
RUN groupadd --system --gid 1001 ait \
 && useradd --system --uid 1001 --gid ait --no-create-home --home /app ait

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # The filesystem audit log must never be selected in a container: it is
    # per-task, so it forks the hash chain across ECS tasks. Blank rather than a
    # path, so a misconfiguration fails loudly instead of writing somewhere
    # ephemeral. See src/ait_voice/db/s3_audit.py.
    AIT_AUDIT_ROOT="" \
    AIT_CONTENT_ROOT=""

WORKDIR /app
COPY --from=build --chown=ait:ait /app/.venv /app/.venv
COPY --from=build --chown=ait:ait /app/src /app/src
# Migrations ship with the image so the migrate task and the app are the same
# artifact — a schema and an application that are versioned apart is how two
# environments diverge with nothing to show for it.
COPY --chown=ait:ait db/migrations/ /app/db/migrations/
COPY --chown=ait:ait compliance/baa-register.toml /app/compliance/baa-register.toml

USER ait
EXPOSE 8000

# The ALB has its own health check; this one is for `docker run` and for local
# compose, where nothing else is watching.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2).status==200 else 1)"

# Overridden per ECS task definition — the voice service will run a different
# command from the same image.
CMD ["uvicorn", "--factory", "ait_voice.api.main:production_app", \
     "--host", "0.0.0.0", "--port", "8000"]
