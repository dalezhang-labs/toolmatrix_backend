"""百度热搜 — data embedded as JSON inside a <!--s-data:...--> comment."""

from __future__ import annotations

import json
import re

from ..base import BaseFetcher, NewsItem
from ..http import fetch_text


_DATA_RE = re.compile(r"<!--s-data:(.*?)-->", re.S)


class BaiduHotFetcher(BaseFetcher):
    slug = "baidu"
    name = "百度热搜"
    lang = "zh"
    category = "china"
    region = "cn"
    interval_sec = 15 * 60
    weight = 1.0
    home_url = "https://top.baidu.com/board?tab=realtime"

    async def fetch(self) -> list[NewsItem]:
        html = await fetch_text("https://top.baidu.com/board?tab=realtime")
        m = _DATA_RE.search(html)
        if not m:
            raise RuntimeError("Baidu: s-data comment not found")
        data = json.loads(m.group(1))

        cards = (data.get("data") or {}).get("cards") or []
        if not cards:
            return []
        content = cards[0].get("content") or []

        items: list[NewsItem] = []
        rank = 0
        for c in content:
            if c.get("isTop"):
                continue
            rank += 1
            word = c.get("word")
            raw_url = c.get("rawUrl") or c.get("url")
            if not (word and raw_url):
                continue
            hot_score_raw = c.get("hotScore")
            try:
                hot_val = float(hot_score_raw) if hot_score_raw is not None else None
            except (TypeError, ValueError):
                hot_val = None
            items.append(
                NewsItem(
                    external_id=raw_url,
                    title=word,
                    url=raw_url,
                    mobile_url=raw_url,
                    summary=c.get("desc"),
                    cover=c.get("img"),
                    hot_raw=hot_val,
                    rank=rank,
                    metrics={"hot_score": hot_score_raw},
                )
            )
        return items
