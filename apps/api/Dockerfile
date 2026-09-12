FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.12.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/workspace/apps/api/.venv/bin:$PATH" \
    PYTHONPATH="/workspace/apps/api/src"

COPY --from=uv /uv /uvx /bin/
WORKDIR /workspace/apps/api

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/scripts ./scripts
COPY apps/api/src ./src
COPY config /workspace/config
COPY data /workspace/data

USER 65532:65532
EXPOSE 8080

CMD ["uvicorn", "civiclens.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
