"""Lobsters hot — 官方 /hottest.json."""

from __future__ import annotations

from datetime import datetime

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


class LobstersFetcher(BaseFetcher):
    slug = "lobsters"
    name = "Lobsters"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 2 * 60 * 60
    weight = 0.9
    home_url = "https://lobste.rs/"

    async def fetch(self) -> list[NewsItem]:
        rows = await fetch_json("https://lobste.rs/hottest.json")
        if not isinstance(rows, list):
            return []

        items: list[NewsItem] = []
        for rank, r in enumerate(rows, start=1):
            short_id = r.get("short_id")
            title = r.get("title")
            if not (short_id and title):
                continue
            created_at = r.get("created_at")
            published = None
            if created_at:
                try:
                    published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    pass
            items.append(
                NewsItem(
                    external_id=short_id,
                    title=title,
                    url=r.get("url") or f"https://lobste.rs/s/{short_id}",
                    mobile_url=r.get("short_id_url"),
                    author=(
                        r.get("submitter_user")
                        if isinstance(r.get("submitter_user"), str)
                        else (r.get("submitter_user") or {}).get("username")
                    ),
                    summary=r.get("description") or r.get("description_plain") or None,
                    published_at=published,
                    hot_raw=float(r.get("score") or 0),
                    rank=rank,
                    metrics={
                        "score": r.get("score"),
                        "comment_count": r.get("comment_count"),
                        "tags": r.get("tags"),
                    },
                )
            )
        return items
