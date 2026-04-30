from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from app.routers import customers, orders, logistics, subscriptions, tenants, stripe_subscriptions, site_users
from app.middleware.auth import AuthMiddleware
from app.middleware.tenant import TenantMiddleware
from app.database import create_tables, close_db
from config import settings
import logging

# 配置日志
logging.basicConfig(
    level=settings.log_level.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    try:
        await create_tables()
        logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Failed to create database tables: {e}")
    yield
    # 关闭时清理数据库连接
    try:
        await close_db()
        logging.info("Database connections closed")
    except Exception as e:
        logging.error(f"Error closing database connections: {e}")

app = FastAPI(
    title="Shopline by OmnigaTech API",
    description="FastAPI backend for Shopline Zendesk integration",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# CORS配置 - 允许开发和生产环境的域名
allowed_origins = [
    "http://localhost:3000",  # 本地开发
    "http://localhost:3001",  # 本地开发备用端口
    "https://zendesk.omnigatech.com",  # 生产环境新域名
    "https://shopline-frontend.vercel.app",  # Vercel部署域名（如果还在使用）
    "https://stripepage-shoplinebyomnigatech.vercel.app",  # 另一个Vercel域名
    "https://omnigatech.zendesk.com",  # OmnigaTech的Zendesk实例
    "https://hllhome.zendesk.com",  # hllhome的Zendesk实例
]

# 自定义CORS中间件以支持所有Zendesk子域名
def is_allowed_origin(origin: str) -> bool:
    """检查origin是否被允许"""
    if not origin:
        return False
    
    # 检查是否在允许列表中
    if origin in allowed_origins:
        return True
    
    # 检查是否是Zendesk的子域名
    import re
    zendesk_pattern = r'^https://[a-zA-Z0-9\-]+\.zendesk\.com$'
    if re.match(zendesk_pattern, origin):
        return True
    
    return False

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://.*\.zendesk\.com$|^https://.*\.apps\.zdusercontent\.com$|^http://localhost:\d+$|^https://zendesk\.omnigatech\.com$|^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],  # 暴露所有响应头
)

# 信任主机中间件 - 生产环境中应该限制具体主机
trusted_hosts = ["*"] if settings.debug else [
    "your-app.onrender.com",
    "localhost"
]

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=trusted_hosts
)

# 自定义中间件
# 注意：中间件按照添加的反向顺序执行
# 所以 TenantMiddleware 先添加，会后执行（在 AuthMiddleware 之后）
app.add_middleware(TenantMiddleware)
app.add_middleware(AuthMiddleware)

# 注册路由
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(logistics.router, prefix="/api/logistics", tags=["logistics"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(tenants.router, prefix="/api/tenants", tags=["tenants"])
app.include_router(stripe_subscriptions.router, prefix="/api/stripe", tags=["stripe"])
app.include_router(site_users.router, prefix="/api/users", tags=["users"])

@app.get("/")
async def root():
    return {
        "message": "Shopline by OmnigaTech API",
        "version": "1.0.0",
        "environment": settings.environment,
        "debug": settings.debug
    }

@app.head("/")
async def root_head():
    return {}

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """处理所有OPTIONS请求的CORS预检"""
    return {}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment
    }

@app.head("/health")
async def health_check_head():
    return {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    ) 