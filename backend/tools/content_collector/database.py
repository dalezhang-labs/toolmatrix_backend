"""Database engine and session factories for content_collector.

Uses a dedicated SQLAlchemy Base and `content_collector` Postgres schema so it
is fully isolated from other tools sharing the Neon database.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.tools.shopline_zendesk.routes.zendesk.app.database import (
    parse_database_url,
)

from .config import content_collector_settings

logger = logging.getLogger(__name__)

SCHEMA = "content_collector"


class Base(DeclarativeBase):
    """Dedicated Base for this tool — keeps metadata isolated."""

    pass


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_raw_url = content_collector_settings.effective_database_url
async_db_url = parse_database_url(_raw_url, is_async=True) if _raw_url else ""

content_collector_engine = create_async_engine(
    async_db_url or "postgresql+asyncpg://unused",
    echo=content_collector_settings.debug,
    future=True,
    connect_args=(
        {"server_settings": {"search_path": f"{SCHEMA},public"}}
        if _raw_url
        else {}
    ),
)

_async_session_factory = sessionmaker(
    content_collector_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_content_collector_db():
    async with _async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# For background jobs (scheduler, ingest) that are not request-scoped
# ---------------------------------------------------------------------------
def session_factory() -> sessionmaker:
    return _async_session_factory


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------
async def create_content_collector_tables() -> None:
    """Create the content_collector schema and all ORM tables.

    Safe to call on every startup — CREATE SCHEMA / CREATE TABLE are idempotent.
    """
    if not _raw_url:
        logger.warning(
            "content_collector: DATABASE_URL not set, skipping table creation"
        )
        return

    # Import models so their tables are attached to Base.metadata before create_all.
    from . import models  # noqa: F401

    async with content_collector_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)

    logger.info("content_collector: schema and tables are ready")
