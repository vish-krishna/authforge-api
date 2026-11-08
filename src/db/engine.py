from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from typing import AsyncGenerator, Optional
from src.config.secrets import SECRETS
from src.logger import logger
from urllib.parse import quote_plus
from src.models.base import Base

# global engine and session maker variables to be initialized during application startup
engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None


def create_db_engine_and_session() -> AsyncEngine:

    global engine, AsyncSessionLocal

    # Check if all required secrets are loaded
    if not all(
        [
            SECRETS.DB_USER,
            SECRETS.DB_PASSWORD,
            SECRETS.DB_HOST,
            SECRETS.DB_PORT,
            SECRETS.DB_NAME,
        ]
    ):
        raise ValueError(
            "Database configuration is incomplete. Please check your secrets variables."
        )

    db_username = quote_plus(SECRETS.DB_USER)
    db_password = quote_plus(SECRETS.DB_PASSWORD)

    DATABASE_URL = f"postgresql+asyncpg://{db_username}:{db_password}@{SECRETS.DB_HOST}:{SECRETS.DB_PORT}/{SECRETS.DB_NAME}"
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,  # logs SQL (disable in prod)
        # pool_pre_ping=True,  # checks dead connections
        pool_size=10,  # adjust based on expected load
        max_overflow=20,  # allows temporary connections beyond pool_size
        pool_pre_ping=True,  # checks if connections are alive before using
        pool_recycle=1800,  # recycle connections after 30 minutes
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    return engine


async def connect_db() -> None:

    global engine
    if not engine:
        engine = create_db_engine_and_session()

    try:
        # Test the connection by acquiring a connection from the pool
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {e}")
        raise e


async def create_all_tables():
    """
    Asynchronously create all database tables.
    """

    if not engine:
        raise RuntimeError(
            "Database engine is not initialized. Call connect_db() first."
        )

    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")


async def close_db():
    """
    Asynchronously dispose of the database engine, closing all connections.
    """
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connections closed successfully.")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide an async database session.
    Ensures the session is properly closed after use.
    """
    if not AsyncSessionLocal:
        raise RuntimeError(
            "AsyncSessionLocal is not initialized. Call connect_db() first."
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


__all__ = ["create_all_tables", "get_session", "connect_db", "close_db"]
