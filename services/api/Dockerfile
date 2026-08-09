FROM ghcr.io/astral-sh/uv:0.9.18-python3.12-bookworm-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN groupadd --system --gid 10001 accessforge \
  && useradd --system --uid 10001 --gid accessforge --create-home --home-dir /home/accessforge accessforge
COPY --chown=accessforge:accessforge accessforge ./accessforge
COPY --chown=accessforge:accessforge migrations ./migrations
COPY --chown=accessforge:accessforge alembic.ini ./alembic.ini
USER accessforge
EXPOSE 10000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn accessforge.main:app --host 0.0.0.0 --port 10000"]
