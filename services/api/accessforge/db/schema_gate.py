"""Fail worker/scheduler startup when the database migration is not current."""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from accessforge.core.config import get_settings


async def database_schema_is_current() -> bool:
    """Compare the connected database revisions with repository migration heads."""

    api_root = Path(__file__).resolve().parents[2]
    alembic_config = AlembicConfig(str(api_root / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_config)
    expected_heads = set(script.get_heads())
    engine = create_async_engine(get_settings().async_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            current_heads = await connection.run_sync(
                lambda sync_connection: set(
                    MigrationContext.configure(sync_connection).get_current_heads()
                )
            )
    finally:
        await engine.dispose()
    return current_heads == expected_heads


def main() -> None:
    if not asyncio.run(database_schema_is_current()):
        raise SystemExit(
            "Database schema is not at the repository migration head; "
            "the API migration owner must deploy successfully first."
        )
    print("Database schema is at the repository migration head.")


if __name__ == "__main__":
    main()
