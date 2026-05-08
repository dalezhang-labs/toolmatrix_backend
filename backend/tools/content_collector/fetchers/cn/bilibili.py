"""B 站热门 — api.bilibili.com/x/web-interface/popular.

Public endpoint, no auth needed.
"""

from __future__ import annotations

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


class BilibiliPopularFetcher(BaseFetcher):
    slug = "bilibili"
    name = "B 站热门"
    lang = "zh"
    category = "tech"
    region = "cn"
    interval_sec = 60 * 60
    weight = 1.0
    home_url = "https://www.bilibili.com/v/popular/all"

    async def fetch(self) -> list[NewsItem]:
        data = await fetch_json(
            "https://api.bilibili.com/x/web-interface/popular?pn=1&ps=30",
            headers={"Referer": "https://www.bilibili.com/"},
        )
        rows = ((data or {}).get("data") or {}).get("list") or []

        items: list[NewsItem] = []
        for rank, r in enumerate(rows, start=1):
            bvid = r.get("bvid")
            title = r.get("title")
            if not (bvid and title):
                continue
            stat = r.get("stat") or {}
            view = stat.get("view") or 0
            like = stat.get("like") or 0
            items.append(
                NewsItem(
                    external_id=bvid,
                    title=title,
                    url=f"https://www.bilibili.com/video/{bvid}",
                    mobile_url=f"https://m.bilibili.com/video/{bvid}",
                    author=(r.get("owner") or {}).get("name"),
                    summary=r.get("desc") or None,
                    cover=r.get("pic"),
                    # Combine view + like*10 as the raw hotness proxy
                    hot_raw=float(view + like * 10),
                    rank=rank,
                    metrics={
                        "view": view,
                        "like": like,
                        "coin": stat.get("coin"),
                        "favorite": stat.get("favorite"),
                        "reply": stat.get("reply"),
                    },
                )
            )
        return items
