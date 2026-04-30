"""One-time data migration from Render PostgreSQL to Neon PostgreSQL (omnigatech schema).

Usage:
    RENDER_DATABASE_URL="postgresql://..." python -m backend.tools.omnigatech.scripts.migrate_data

Reads RENDER_DATABASE_URL for the source (Render) and uses the omnigatech engine
configuration for the target (Neon).  Each table is migrated in its own transaction;
failures are logged and do not block remaining tables.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("omnigatech.migrate")

# Tables to migrate, in dependency order (parents before children)
TABLES_TO_MIGRATE: list[str] = [
    "tenants",
    "users",
    "site_users",
    "user_tenants",
    "subscriptions",
    "subscription_plans",
    "user_subscriptions",
    "user_stripe_subscriptions",
    "payment_history",
    "webhook_events",
]


async def _fetch_all(conn: asyncpg.Connection, table: str) -> list[asyncpg.Record]:
    """Fetch every row from *table* in the source database."""
    return await conn.fetch(f'SELECT * FROM "{table}"')


async def _get_columns(conn: asyncpg.Connection, table: str) -> list[str]:
    """Return column names for *table* from information_schema."""
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = $1
          AND table_schema = 'public'
        ORDER BY ordinal_position
        """,
        table,
    )
    return [r["column_name"] for r in rows]


async def _insert_rows(
    conn: asyncpg.Connection,
    table: str,
    columns: list[str],
    rows: list[asyncpg.Record],
) -> int:
    """Insert *rows* into omnigatech.*table* on the target database.

    Uses a single COPY-style batch insert for speed.  Returns the number of
    rows inserted.
    """
    if not rows:
        return 0

    # Build column list and numbered placeholders
    col_list = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    query = f'INSERT INTO omnigatech."{table}" ({col_list}) VALUES ({placeholders})'

    # Convert Record objects to plain tuples in column order
    values = [[row[c] for c in columns] for row in rows]

    await conn.executemany(query, values)
    return len(values)


async def _count_rows(conn: asyncpg.Connection, table: str, schema: str = "public") -> int:
    """Return the row count for *schema*.*table*."""
    row = await conn.fetchrow(f'SELECT count(*) AS cnt FROM {schema}."{table}"')
    return row["cnt"]


async def migrate_table(
    source_conn: asyncpg.Connection,
    target_conn: asyncpg.Connection,
    table: str,
) -> bool:
    """Migrate a single table inside its own transaction on the target.

    Returns True on success, False on failure (after rollback).
    """
    logger.info("--- Migrating table: %s ---", table)

    try:
        # 1. Read source columns and rows
        columns = await _get_columns(source_conn, table)
        if not columns:
            logger.warning("  Table '%s' not found in source or has no columns – skipping", table)
            return True  # Not an error; table may simply not exist on Render

        source_rows = await _fetch_all(source_conn, table)
        source_count = len(source_rows)
        logger.info("  Source rows: %d", source_count)

        if source_count == 0:
            logger.info("  Nothing to migrate for '%s'", table)
            return True

        # 2. Insert into target inside a transaction
        tx = target_conn.transaction()
        await tx.start()
        try:
            inserted = await _insert_rows(target_conn, table, columns, source_rows)
            logger.info("  Inserted rows: %d", inserted)

            # 3. Verify row count
            target_count = await _count_rows(target_conn, table, schema="omnigatech")
            if target_count < source_count:
                logger.error(
                    "  Row count mismatch for '%s': source=%d, target=%d",
                    table,
                    source_count,
                    target_count,
                )
                await tx.rollback()
                return False

            await tx.commit()
            logger.info("  ✓ '%s' migrated successfully (%d rows)", table, inserted)
            return True

        except Exception:
            await tx.rollback()
            raise

    except Exception as exc:
        logger.error("  ✗ Failed to migrate '%s': %s", table, exc, exc_info=True)
        return False


async def migrate_all_tables() -> None:
    """Connect to source and target databases and migrate every table."""
    render_url = os.getenv("RENDER_DATABASE_URL")
    if not render_url:
        logger.error("RENDER_DATABASE_URL environment variable is not set")
        sys.exit(1)

    # Target URL: prefer OMNIGATECH_DATABASE_URL, fall back to DATABASE_URL
    target_url = os.getenv("OMNIGATECH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not target_url:
        logger.error(
            "Neither OMNIGATECH_DATABASE_URL nor DATABASE_URL is set for the target"
        )
        sys.exit(1)

    logger.info("Connecting to source (Render) …")
    source_conn = await asyncpg.connect(render_url)

    logger.info("Connecting to target (Neon) …")
    # Set search_path so unqualified references resolve to omnigatech
    target_conn = await asyncpg.connect(
        target_url,
        server_settings={"search_path": "omnigatech,public"},
    )

    # Ensure the omnigatech schema exists on the target
    await target_conn.execute("CREATE SCHEMA IF NOT EXISTS omnigatech")

    succeeded: list[str] = []
    failed: list[str] = []

    try:
        for table in TABLES_TO_MIGRATE:
            ok = await migrate_table(source_conn, target_conn, table)
            if ok:
                succeeded.append(table)
            else:
                failed.append(table)
    finally:
        await source_conn.close()
        await target_conn.close()

    # Summary
    logger.info("=" * 60)
    logger.info("Migration summary")
    logger.info("  Succeeded (%d): %s", len(succeeded), ", ".join(succeeded) or "–")
    logger.info("  Failed    (%d): %s", len(failed), ", ".join(failed) or "–")
    logger.info("=" * 60)

    if failed:
        logger.warning("Some tables failed to migrate. Review the logs above.")
        sys.exit(1)
    else:
        logger.info("All tables migrated successfully!")


if __name__ == "__main__":
    asyncio.run(migrate_all_tables())
