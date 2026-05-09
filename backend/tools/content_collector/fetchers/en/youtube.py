"""YouTube Trending — via official Data API v3 (free tier).

Requires YOUTUBE_API_KEY env var. Quota: 10,000 units/day free. A single
`videos.list` call with chart=mostPopular costs ~3 units; we run every 6h =
12 units/day. Plenty of headroom.

Skipped gracefully if the key is missing (source will show red, backlog
stays uncategorized).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


class _YouTubeTrending(BaseFetcher):
    """Base; subclass sets `region_code`."""

    region_code: str = "US"

    lang = "en"
    category = "world"
    region = "global"
    interval_sec = 6 * 60 * 60
    weight = 1.0
    fetcher_type = "native"

    async def fetch(self) -> list[NewsItem]:
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY not set — skipping YouTube")

        data = await fetch_json(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "regionCode": self.region_code,
                "maxResults": 30,
                "key": api_key,
            },
        )
        videos = (data or {}).get("items") or []

        items: list[NewsItem] = []
        for rank, v in enumerate(videos, start=1):
            vid = v.get("id")
            snippet = v.get("snippet") or {}
            stats = v.get("statistics") or {}
            title = snippet.get("title")
            if not (vid and title):
                continue

            try:
                view_count = int(stats.get("viewCount", 0))
            except (TypeError, ValueError):
                view_count = 0
            try:
                like_count = int(stats.get("likeCount", 0))
            except (TypeError, ValueError):
                like_count = 0
            try:
                comment_count = int(stats.get("commentCount", 0))
            except (TypeError, ValueError):
                comment_count = 0

            # Composite hot score: views weigh most but likes+comments
            # indicate engagement quality (not just reach).
            hot_raw = float(view_count + like_count * 10 + comment_count * 20)

            published_at = None
            if snippet.get("publishedAt"):
                try:
                    published_at = datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                except ValueError:
                    pass

            thumbs = snippet.get("thumbnails") or {}
            cover = (
                (thumbs.get("maxres") or thumbs.get("high") or thumbs.get("medium") or {}).get("url")
            )

            items.append(
                NewsItem(
                    external_id=vid,
                    title=title,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    mobile_url=f"https://m.youtube.com/watch?v={vid}",
                    author=snippet.get("channelTitle"),
                    summary=snippet.get("description") or None,
                    cover=cover,
                    published_at=published_at,
                    hot_raw=hot_raw,
                    rank=rank,
                    metrics={
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                    },
                    extra={
                        "category_id": snippet.get("categoryId"),
                        "channel_id": snippet.get("channelId"),
                    },
                )
            )
        return items


class YouTubeTrendingUS(_YouTubeTrending):
    slug = "youtube_us"
    name = "YouTube Trending · US"
    region_code = "US"
    home_url = "https://www.youtube.com/feed/trending"
