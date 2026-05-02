"""
Database configuration using async SQLAlchemy.

Why async? FastAPI is fully async. Using an async DB driver (asyncpg)
means DB queries never block the event loop — the server can handle
other WebSocket messages and requests while waiting for a query to return.

Pattern used: async context-manager sessions via get_db() dependency.
Each request gets its own session, committed on success, rolled back on error.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncAttrs,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
from typing import AsyncGenerator

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,       # verify connection alive before using from pool
    pool_recycle=3600,        # recycle connections every hour
    echo=settings.DEBUG,      # log SQL only in debug mode
)


# ── Session Factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # keep objects usable after commit (important for returning data)
    autoflush=True,
    autocommit=False,
)


# ── Base Model ────────────────────────────────────────────────────────────────

class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    AsyncAttrs enables awaiting lazy-loaded relationships.
    """
    pass


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a DB session per request.

    Usage in a router:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically committed on success and
    rolled back if any exception is raised.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Health Check ──────────────────────────────────────────────────────────────

async def check_db_connection() -> bool:
    """Returns True if database is reachable. Used by /health endpoint."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed | error={str(e)}")
        return False


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables. Called at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised")


async def close_db() -> None:
    """Dispose the connection pool. Called at application shutdown."""
    await engine.dispose()
    logger.info("Database connection pool closed")
