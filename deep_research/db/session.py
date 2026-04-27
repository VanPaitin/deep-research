from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from deep_research.config import get_database_url


engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global engine

    if engine is None:
        engine = create_async_engine(
            get_database_url(),
            pool_pre_ping=True,
        )

    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
        )

    return AsyncSessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as session:
        yield session


async def check_database_connection() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("select 1"))
