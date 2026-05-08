"""Weibo hot search.

Uses the public AJAX endpoint with a long-lived anonymous SUB cookie (copied
from newsnow, which has proven stable in the wild for 2+ years). No login
required, but Weibo rejects the request without a Referer.
"""

from __future__ import annotations

from urllib.parse import quote

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


# Long-lived anonymous SUB cookie used by newsnow. If Weibo ever rotates this,
# fetching a fresh one is a 1-minute job (curl weibo.com → grab Set-Cookie).
_ANON_SUB = (
    "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHid"
)


class WeiboHotFetcher(BaseFetcher):
    slug = "weibo"
    name = "微博热搜"
    lang = "zh"
    category = "china"
    region = "cn"
    interval_sec = 15 * 60
    weight = 1.2  # Weibo hot search has strong broad-audience signal
    home_url = "https://s.weibo.com/top/summary/"

    async def fetch(self) -> list[NewsItem]:
        data = await fetch_json(
            "https://weibo.com/ajax/side/hotSearch",
            headers={
                "Referer": "https://weibo.com/",
                "Cookie": _ANON_SUB,
            },
        )
        realtime = (data or {}).get("data", {}).get("realtime") or []

        items: list[NewsItem] = []
        for rank, row in enumerate(realtime, start=1):
            word = row.get("word") or row.get("word_scheme")
            if not word:
                continue
            # Weibo's "num" is the search index (higher = hotter)
            num = row.get("num")
            try:
                num_val = float(num) if num is not None else None
            except (TypeError, ValueError):
                num_val = None

            q = quote(word)
            url = f"https://s.weibo.com/weibo?q={q}"

            items.append(
                NewsItem(
                    external_id=row.get("mid") or row.get("word_scheme") or word,
                    title=word,
                    url=url,
                    mobile_url=url,
                    hot_raw=num_val,
                    rank=rank,
                    metrics={"search_index": num_val} if num_val is not None else {},
                    extra={"flag": row.get("icon_desc") or row.get("label_name")},
                )
            )
        return items
