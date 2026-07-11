from contextlib import asynccontextmanager
from functools import cache

from fastmcp.dependencies import Depends as MCPDepends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tg_mcp.config import get_server_settings, server_settings
from tg_mcp.orm.base import Base


@cache
def get_engine() -> AsyncEngine:
    return create_async_engine(
        server_settings.db_url, echo=server_settings.db_echo, pool_pre_ping=True
    )


@cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=True)


async def session_dep():
    session_factory = get_session_factory()
    async with session_factory() as s, s.begin():
        yield s


session = asynccontextmanager(session_dep)
MCPSessionDep = MCPDepends(session)


async def init_db() -> None:
    """Create tables if they don't exist yet.

    No migration tool for now: the schema is small and this is a personal
    single-deployment service. Reach for Alembic later if that changes.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await get_engine().dispose()


__all__ = ["MCPSessionDep", "session", "init_db", "dispose_engine"]
