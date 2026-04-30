import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 数据库配置
    database_url: str = os.getenv(
        "DATABASE_URL", 
        ""
    )
    
    # Redis 配置
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    
    # 安全配置
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # 服务器配置
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", "6100"))
    
    # Shopline API 配置
    shopline_api_base_url: str = os.getenv("SHOPLINE_API_BASE_URL", "https://api.shopline.com")
    shopline_api_version: str = os.getenv("SHOPLINE_API_VERSION", "v1")
    
    # Zendesk 配置
    zendesk_webhook_secret: Optional[str] = os.getenv("ZENDESK_WEBHOOK_SECRET")
    
    # 日志配置
    log_level: str = os.getenv("LOG_LEVEL", "DEBUG")
    
    # 环境标识
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Stripe配置
    stripe_secret_key: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # 邮件配置
    resend_api_key: Optional[str] = os.getenv("RESEND_API_KEY")
    email_from: str = os.getenv("EMAIL_FROM", "noreply@omnigatech.com")
    frontend_url: str = os.getenv("FRONTEND_URL", "https://zendesk.omnigatech.com")
    
    class Config:
        env_file = ".env"

settings = Settings() 
