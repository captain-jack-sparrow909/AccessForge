import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from accessforge.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def sync_database_url(url: str) -> str:
    """Alembic uses synchronous drivers while the API uses async SQLAlchemy drivers."""
    return url.replace("+aiosqlite", "").replace("+asyncpg", "")


def configured_database_url() -> str:
    """Prefer the deployment database URL over Alembic's local fallback."""

    return os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    url = sync_database_url(configured_database_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    if section is None:
        section = {}
    section["sqlalchemy.url"] = sync_database_url(configured_database_url())
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
