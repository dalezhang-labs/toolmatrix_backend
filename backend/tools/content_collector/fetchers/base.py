"""Fetcher base: NewsItem dataclass, FetchResult, and BaseFetcher contract.

Inspired by newsnow's `defineSource()` pattern. Every source file declares one
or more fetchers (subclassed or via helpers) that produce a list of NewsItem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class NewsItem:
    """A single piece of content fetched from a source.

    `hot_raw` is whatever the platform reports (upvotes, 热度值, 人气, score...).
    The ingest layer will normalize it into `hot_score` (0-100) based on source
    weight and distribution within the fetch batch.
    """

    external_id: str
    title: str
    url: str

    mobile_url: Optional[str] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    cover: Optional[str] = None
    published_at: Optional[datetime] = None

    hot_raw: Optional[float] = None
    rank: Optional[int] = None  # position in the source's own list at fetch time
    metrics: dict[str, Any] = field(default_factory=dict)  # likes/comments/shares

    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    slug: str
    items: list[NewsItem]
    fetched_at: datetime


class BaseFetcher:
    """Contract for a source fetcher.

    Subclasses declare class-level metadata and implement `fetch()`. The
    registry picks them up automatically when the module is imported.
    """

    # --- metadata (override in subclass) ---
    slug: str = ""
    name: str = ""
    lang: str = "en"  # "zh" | "en"
    category: str = "tech"  # china|world|tech|finance
    region: str = "global"  # cn|us|global
    fetcher_type: str = "native"  # native|rss|rsshub
    interval_sec: int = 1800
    weight: float = 1.0
    home_url: Optional[str] = None
    fetcher_config: dict = {}

    # Auto-registration is handled by FetcherRegistry importing the module.

    async def fetch(self) -> list[NewsItem]:
        raise NotImplementedError
