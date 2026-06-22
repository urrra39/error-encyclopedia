"""Async SQLAlchemy engine, session factory, and database lifecycle helpers.

This module owns every piece of PostgreSQL connectivity:

* ``Settings``          — environment-driven configuration (Pydantic).
* ``Base``              — the declarative base shared by all ORM models.
* ``engine``            — a process-wide async engine (asyncpg driver).
* ``AsyncSessionLocal`` — the async session factory.
* ``get_db``           — a FastAPI dependency that yields a transactional session
                          and converts low-level driver failures into clean errors.
* ``init_db`` / ``check_database_connection`` / ``dispose_engine`` — lifecycle hooks.

All database access is fully asynchronous. Connection failures are caught and
re-raised as :class:`DatabaseConnectionError` so callers never leak raw driver
exceptions to API clients.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("error_encyclopedia.database")


class DatabaseConnectionError(RuntimeError):
    """Raised when the application cannot reach or query PostgreSQL."""


class Settings(BaseSettings):
    """Database configuration loaded from the environment / ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "error_enc"
    POSTGRES_PASSWORD: str = "error_enc"
    POSTGRES_DB: str = "error_encyclopedia"

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False

    @field_validator("POSTGRES_PORT")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("POSTGRES_PORT must be between 1 and 65535")
        return value

    @property
    def async_database_url(self) -> str:
        """Async DSN using the asyncpg driver."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, validated ``Settings`` singleton."""
    return Settings()


settings = get_settings()

# Deterministic constraint naming → clean, reversible Alembic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the project."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=settings.DB_ECHO,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional async session.

    Commits on success, rolls back on any error, and always closes the session.
    Driver/connection failures are surfaced as :class:`DatabaseConnectionError`.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("Database error during request handling")
        raise DatabaseConnectionError("A database error occurred.") from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_database_connection() -> bool:
    """Return ``True`` if a trivial ``SELECT 1`` succeeds, else raise.

    Used by health checks and startup probes to fail fast when PostgreSQL is
    unreachable.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.exception("PostgreSQL connectivity check failed")
        raise DatabaseConnectionError(
            "Could not establish a connection to PostgreSQL."
        ) from exc


async def init_db() -> None:
    """Create all tables defined on ``Base.metadata`` if they do not yet exist.

    Importing the models module registers the tables on the shared metadata; the
    local import here avoids a circular import at module load time.
    """
    import models  # noqa: F401  (registers ORM tables on Base.metadata)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except SQLAlchemyError as exc:
        logger.exception("Failed to initialize database schema")
        raise DatabaseConnectionError("Database schema initialization failed.") from exc


async def dispose_engine() -> None:
    """Dispose of the engine's connection pool (call on application shutdown)."""
    await engine.dispose()
