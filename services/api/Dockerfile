FROM ghcr.io/astral-sh/uv:0.9.18-python3.12-bookworm-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY accessforge ./accessforge
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
EXPOSE 10000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn accessforge.main:app --host 0.0.0.0 --port 10000"]
