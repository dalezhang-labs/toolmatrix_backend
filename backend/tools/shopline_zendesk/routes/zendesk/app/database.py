from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from ..config import settings
from .models.base import Base
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def parse_database_url(url: str, is_async: bool = False):
    """Parse database URL and handle SSL parameters correctly"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Remove sslmode for asyncpg, convert to ssl parameter
    if is_async:
        # Convert postgresql:// to postgresql+asyncpg://
        scheme = parsed.scheme.replace("postgresql://", "postgresql+asyncpg://")
        if not scheme.startswith("postgresql+asyncpg"):
            scheme = "postgresql+asyncpg"
        
        # Handle SSL for asyncpg
        if 'sslmode' in query_params:
            del query_params['sslmode']
            # asyncpg uses ssl=require instead of sslmode=require
            query_params['ssl'] = ['require']

        # asyncpg does not accept libpq-specific channel_binding query parameter
        if 'channel_binding' in query_params:
            del query_params['channel_binding']
        
        # Rebuild URL without sslmode but with ssl for asyncpg
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(scheme=scheme, query=new_query)
    else:
        # For sync connection, keep sslmode but remove it from query string
        # as it should be passed as connect_args
        if 'sslmode' in query_params:
            del query_params['sslmode']
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
    
    return urlunparse(new_parsed)

# Parse the database URLs
async_db_url = parse_database_url(settings.database_url, is_async=True)
sync_db_url = parse_database_url(settings.database_url, is_async=False)

# 创建异步数据库引擎
engine = create_async_engine(
    async_db_url,
    echo=settings.debug,
    future=True
)

# 创建同步数据库引擎（供中间件使用）
# Handle sslmode in connect_args for psycopg2
connect_args = {}
if 'sslmode=require' in settings.database_url:
    connect_args['sslmode'] = 'require'

sync_engine = create_engine(
    sync_db_url,
    echo=settings.debug,
    connect_args=connect_args
)

# 创建异步会话工厂
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 创建同步会话工厂
sync_session = sessionmaker(
    sync_engine, class_=Session, expire_on_commit=False
)

# 异步数据库依赖
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# 同步数据库依赖（供中间件使用）
def get_sync_db():
    session = sync_session()
    try:
        yield session
    finally:
        session.close()

# 创建数据库表
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Supplementary tables queried by stripe/user routers (not in SQLAlchemy models).
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.subscription_plans (
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
            CREATE TABLE IF NOT EXISTS public.plan_features (
                id uuid PRIMARY KEY,
                plan_id uuid REFERENCES public.subscription_plans(id),
                feature_key varchar(255) NOT NULL,
                feature_value text,
                feature_type varchar(100),
                description text,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.user_subscriptions (
                id uuid PRIMARY KEY,
                user_id text NOT NULL,
                stripe_subscription_id varchar(255) NOT NULL UNIQUE,
                stripe_customer_id varchar(255) NOT NULL,
                plan_id uuid REFERENCES public.subscription_plans(id),
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
            CREATE TABLE IF NOT EXISTS public.payment_history (
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
            CREATE TABLE IF NOT EXISTS public.webhook_events (
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

# 关闭数据库连接
async def close_db():
    await engine.dispose()
    sync_engine.dispose() 
