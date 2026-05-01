import logging

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from backend.tools.shopline_zendesk.routes.zendesk.app.database import (
    parse_database_url,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.models.base import Base
from .config import omnigatech_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------
_raw_url = omnigatech_settings.effective_database_url

async_db_url = parse_database_url(_raw_url, is_async=True)
sync_db_url = parse_database_url(_raw_url, is_async=False)

# ---------------------------------------------------------------------------
# Async engine (for route handlers)
# ---------------------------------------------------------------------------
omnigatech_engine = create_async_engine(
    async_db_url,
    echo=omnigatech_settings.debug,
    future=True,
    connect_args={"server_settings": {"search_path": "omnigatech,public"}},
)

# ---------------------------------------------------------------------------
# Sync engine (for middleware) — psycopg2 uses 'options' in the DSN, not connect_args
# ---------------------------------------------------------------------------
_sync_url_with_schema = sync_db_url
if "?" in _sync_url_with_schema:
    _sync_url_with_schema += "&options=-c%20search_path%3Domnigatech%2Cpublic"
else:
    _sync_url_with_schema += "?options=-c%20search_path%3Domnigatech%2Cpublic"

omnigatech_sync_engine = create_engine(
    _sync_url_with_schema,
    echo=omnigatech_settings.debug,
)

# ---------------------------------------------------------------------------
# Session factories
# ---------------------------------------------------------------------------
_async_session_factory = sessionmaker(
    omnigatech_engine, class_=AsyncSession, expire_on_commit=False
)

_sync_session_factory = sessionmaker(
    omnigatech_sync_engine, class_=Session, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_omnigatech_db():
    """Async DB dependency for route handlers."""
    async with _async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_omnigatech_sync_db():
    """Sync DB dependency for middleware."""
    session = _sync_session_factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------
async def create_omnigatech_tables():
    """Create the omnigatech schema and all required tables."""
    async with omnigatech_engine.begin() as conn:
        # 1. Ensure the schema exists
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS omnigatech"))

        # 2. Create SQLAlchemy-mapped tables (tenants, site_users, etc.)
        await conn.run_sync(Base.metadata.create_all)

        # 3. Supplementary tables via raw SQL (same DDL as shopline_zendesk
        #    create_tables(), but targeting the omnigatech schema)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS omnigatech.subscription_plans (
                id uuid PRIMARY KEY,
                stripe_price_id varchar(255),
                stripe_product_id varchar(255),
                name varchar(255) NOT NULL,
                description text,
                amount integer NOT NULL,
                currency varchar(10) NOT NULL DEFAULT 'usd',
                interval varchar(20) NOT NULL,
                interval_count integer NOT NULL DEFAULT 1,
                trial_period_days integer,
                is_active boolean NOT NULL DEFAULT true,
                metadata jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS omnigatech.plan_features (
                id uuid PRIMARY KEY,
                plan_id uuid REFERENCES omnigatech.subscription_plans(id),
                feature_key varchar(255) NOT NULL,
                feature_value text,
                feature_type varchar(100),
                description text,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS omnigatech.user_subscriptions (
                id uuid PRIMARY KEY,
                user_id text NOT NULL,
                stripe_subscription_id varchar(255) NOT NULL UNIQUE,
                stripe_customer_id varchar(255) NOT NULL,
                plan_id uuid REFERENCES omnigatech.subscription_plans(id),
                status varchar(50) NOT NULL,
                current_period_start timestamptz NOT NULL,
                current_period_end timestamptz NOT NULL,
                trial_start timestamptz,
                trial_end timestamptz,
                cancel_at_period_end boolean,
                canceled_at timestamptz,
                ended_at timestamptz,
                amount integer NOT NULL,
                currency varchar(3) NOT NULL,
                interval varchar(20) NOT NULL,
                interval_count integer NOT NULL,
                metadata jsonb,
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now()
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS omnigatech.payment_history (
                id uuid PRIMARY KEY,
                user_id text NOT NULL,
                subscription_id uuid,
                stripe_invoice_id varchar(255),
                stripe_payment_intent_id varchar(255),
                stripe_charge_id varchar(255),
                amount integer NOT NULL,
                currency varchar(3) NOT NULL,
                status varchar(50) NOT NULL,
                payment_method_type varchar(50),
                payment_method_last4 varchar(4),
                payment_method_brand varchar(50),
                period_start timestamptz,
                period_end timestamptz,
                attempted_at timestamptz,
                succeeded_at timestamptz,
                failed_at timestamptz,
                created_at timestamptz DEFAULT now(),
                failure_reason text,
                receipt_url text,
                metadata jsonb
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS omnigatech.webhook_events (
                id uuid PRIMARY KEY,
                stripe_event_id varchar(255) UNIQUE NOT NULL,
                event_type varchar(255) NOT NULL,
                processed boolean NOT NULL DEFAULT false,
                processed_at timestamptz,
                error_message text,
                retry_count integer NOT NULL DEFAULT 0,
                event_data jsonb,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """))

    logger.info("OmnigaTech schema and tables are ready")
