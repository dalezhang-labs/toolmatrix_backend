"""Configuration for the content_collector tool.

All env vars are namespaced with CONTENT_COLLECTOR_ to keep them isolated from
other tools in the shared backend.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class ContentCollectorSettings(BaseSettings):
    # Database: prefer CONTENT_COLLECTOR_DATABASE_URL, fall back to DATABASE_URL
    content_collector_database_url: Optional[str] = os.getenv(
        "CONTENT_COLLECTOR_DATABASE_URL"
    )
    database_url: str = os.getenv("DATABASE_URL", "")

    @property
    def effective_database_url(self) -> str:
        return self.content_collector_database_url or self.database_url

    # Scheduler: disable in dev if you want, default on
    scheduler_enabled: bool = (
        os.getenv("CONTENT_COLLECTOR_SCHEDULER_ENABLED", "true").lower() == "true"
    )

    # How many days of items to keep (GC'd by a background task, not yet wired)
    retention_days: int = int(os.getenv("CONTENT_COLLECTOR_RETENTION_DAYS", "14"))

    # Optional API keys / cookies — all optional, sources degrade gracefully
    producthunt_token: Optional[str] = os.getenv("PRODUCTHUNT_API_TOKEN")
    zhihu_cookie: Optional[str] = os.getenv("CONTENT_COLLECTOR_ZHIHU_COOKIE")

    # HTTP client defaults
    http_timeout_sec: int = int(os.getenv("CONTENT_COLLECTOR_HTTP_TIMEOUT", "10"))
    http_user_agent: str = os.getenv(
        "CONTENT_COLLECTOR_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    )

    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        extra = "ignore"


content_collector_settings = ContentCollectorSettings()
