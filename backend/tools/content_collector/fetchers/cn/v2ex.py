"""V2EX 热门主题 — 官方 /api/topics/hot.json."""

from __future__ import annotations

from datetime import datetime, timezone

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


class V2EXHotFetcher(BaseFetcher):
    slug = "v2ex"
    name = "V2EX 热门"
    lang = "zh"
    category = "tech"
    region = "cn"
    interval_sec = 60 * 60
    weight = 0.8
    home_url = "https://www.v2ex.com/?tab=hot"

    async def fetch(self) -> list[NewsItem]:
        rows = await fetch_json("https://www.v2ex.com/api/topics/hot.json")
        if not isinstance(rows, list):
            return []

        items: list[NewsItem] = []
        for rank, r in enumerate(rows, start=1):
            tid = r.get("id")
            title = r.get("title")
            url = r.get("url")
            if not (tid and title and url):
                continue
            created = r.get("created")
            published = (
                datetime.fromtimestamp(int(created), tz=timezone.utc)
                if isinstance(created, (int, float))
                else None
            )
            items.append(
                NewsItem(
                    external_id=str(tid),
                    title=title,
                    url=url,
                    mobile_url=url,
                    author=(r.get("member") or {}).get("username"),
                    summary=(r.get("content") or "")[:300] or None,
                    published_at=published,
                    hot_raw=float(r.get("replies") or 0),
                    rank=rank,
                    metrics={"replies": r.get("replies")},
                )
            )
        return items
