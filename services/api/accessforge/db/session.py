from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from accessforge.core.config import get_settings
from accessforge.db.models import Base

settings = get_settings()
engine: AsyncEngine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def initialize_database() -> None:
    if not settings.auto_create_db:
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def database_is_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
