FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY migrations ./migrations

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run python -m app.migrate && exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
