"""少数派首页 — 官方 JSON-feed 接口 /api/v1/article/index/page/get."""

from __future__ import annotations

from datetime import datetime, timezone

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


class SSPaiFetcher(BaseFetcher):
    slug = "sspai"
    name = "少数派首页"
    lang = "zh"
    category = "tech"
    region = "cn"
    interval_sec = 60 * 60
    weight = 0.9
    home_url = "https://sspai.com/"

    async def fetch(self) -> list[NewsItem]:
        data = await fetch_json(
            "https://sspai.com/api/v1/article/index/page/get"
            "?limit=30&offset=0&created_at=0&tag=%E5%85%A8%E9%83%A8"
        )
        rows = (data or {}).get("data") or []

        items: list[NewsItem] = []
        for rank, r in enumerate(rows, start=1):
            aid = r.get("id")
            title = r.get("title")
            if not (aid and title):
                continue
            created = r.get("released_time") or r.get("created_at")
            published = (
                datetime.fromtimestamp(int(created), tz=timezone.utc)
                if isinstance(created, (int, float))
                else None
            )
            items.append(
                NewsItem(
                    external_id=str(aid),
                    title=title,
                    url=f"https://sspai.com/post/{aid}",
                    mobile_url=f"https://sspai.com/post/{aid}",
                    author=(r.get("author") or {}).get("nickname"),
                    summary=r.get("summary") or r.get("description"),
                    cover=r.get("banner"),
                    published_at=published,
                    hot_raw=float(r.get("like_count") or 0),
                    rank=rank,
                    metrics={
                        "like_count": r.get("like_count"),
                        "comment_count": r.get("comment_count"),
                    },
                )
            )
        return items
