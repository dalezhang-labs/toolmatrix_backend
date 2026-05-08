"""Source model — one row per configured data source (Weibo, HN, etc.)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import SCHEMA, Base


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Stable identifier used by fetchers (e.g. "hackernews", "weibo")
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    lang: Mapped[str] = mapped_column(String(4), nullable=False)  # "zh" | "en"
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # china|world|tech|finance
    region: Mapped[str] = mapped_column(String(16), nullable=False)  # cn|us|global

    # How a fetcher knows what to do. For "native", the logic lives in fetchers/*.
    # For "rss" / "rsshub", the url is in fetcher_config.
    fetcher_type: Mapped[str] = mapped_column(String(16), nullable=False)  # native|rss|rsshub
    fetcher_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    interval_sec: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    home_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
