"""Database connection and session management module using SQLAlchemy 2.0 and asyncpg."""

from collections.abc import AsyncGenerator

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.secrets import SECRETS
from src.logger import logger
from src.models.base import Base

# Global engine handle (initialized once during lifespan)
engine: AsyncEngine | None = None

# Global async session factory bound to the engine
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> URL | str:
    """Builds a database connection URL securely from the loaded secrets."""
    # Check if a complete DATABASE_URL string was directly provided in secrets
    direct_url = SECRETS.get("DATABASE_URL")
    if direct_url:
        # Guarantee that PostgreSQL URLs use the asyncpg async driver
        if direct_url.startswith("postgresql://"):
            return direct_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return direct_url

    # Check whether discrete connection parameters are provided in secrets
    db_user = SECRETS.get("DB_USER")
    db_password = SECRETS.get("DB_PASSWORD")
    db_host = SECRETS.get("DB_HOST")
    db_port = SECRETS.get("DB_PORT", 5432)
    db_name = SECRETS.get("DB_NAME")

    # Validate that all required discrete parameters exist
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError(
            "Incomplete database configuration: DATABASE_URL or (DB_USER, DB_PASSWORD, "
            "DB_HOST, DB_PORT, DB_NAME) must be present in secrets."
        )

    # Use SQLAlchemy's URL.create to safely encode passwords with special characters
    return URL.create(
        drivername="postgresql+asyncpg",
        username=db_user,
        password=db_password,
        host=db_host,
        port=int(db_port),
        database=db_name,
    )


async def connect_db() -> None:
    """Initializes the AsyncEngine and verifies database connectivity."""
    global engine, AsyncSessionLocal

    # Idempotency check: avoid re-initializing if already connected
    if engine is not None:
        logger.warning("Database engine is already initialized.")
        return

    database_url = get_database_url()

    logger.info("Initializing async database engine...")

    # Configure connection pool with resilient production settings
    engine = create_async_engine(
        database_url,
        echo=False,  # Keep SQL statements out of standard production logs
        pool_size=10,  # Baseline connections maintained in the pool
        max_overflow=20,  # Max additional surge connections during peak traffic
        pool_pre_ping=True,  # Proactively test connections to drop dead/stale sockets
        pool_recycle=1800,  # Recycle connections every 30 minutes to prevent timeouts
    )

    # Instantiate the session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Prevent eager attribute expiration after commits
        autoflush=False,  # Require explicit flush/commit to prevent unexpected queries
    )

    # Connectivity probe to ensure database is reachable on startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info("Database connection pool established successfully.")


async def close_db() -> None:
    """Gracefully closes all connections in the pool during application shutdown."""
    global engine, AsyncSessionLocal

    # Check if the engine was ever initialized
    if engine is None:
        logger.warning("Database engine was not initialized; skipping teardown.")
        return

    logger.info("Disposing database connection pool...")
    # Close and release all active pooled connections
    await engine.dispose()

    # Reset globals to clean initial state
    engine = None
    AsyncSessionLocal = None
    logger.info("Database connection pool closed successfully.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional AsyncSession.

    Automatically commits on successful requests and rolls back on unhandled exceptions.
    """
    # Guard against queries executed prior to lifespan execution
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database is not initialized. Ensure connect_db() ran during lifespan startup."
        )

    # Acquire an isolated session from the pool
    async with AsyncSessionLocal() as session:
        try:
            # Yield session to route handlers
            yield session
            # Auto-commit if no unhandled exceptions occurred in the route
            await session.commit()
        except Exception:
            # Auto-rollback any pending dirty state on error
            await session.rollback()
            raise
        finally:
            # Ensure the session is cleanly closed and returned to the pool
            await session.close()


async def create_all_tables() -> None:
    """Creates tables via SQLAlchemy metadata (development/testing only)."""
    # Verify engine is ready
    if engine is None:
        raise RuntimeError("Database engine is not initialized.")

    # Execute DDL generation synchronously via the async connection runner
    async with engine.begin() as conn:
        logger.info("Running table creation DDL...")
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables verified/created.")


__all__ = [
    "Base",
    "connect_db",
    "close_db",
    "get_db",
    "create_all_tables",
    "engine",
    "AsyncSessionLocal",
]