"""知乎热榜 — api.zhihu.com/topstory/hot-list-web.

Works anonymously (returns ~20 items). Setting CONTENT_COLLECTOR_ZHIHU_COOKIE
bumps that to ~50 items and is strongly recommended.
"""

from __future__ import annotations

import re

from ...config import content_collector_settings
from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


_HOT_RE = re.compile(r"([\d.]+)\s*万")


def _parse_hot(text: str | None) -> float | None:
    if not text:
        return None
    m = _HOT_RE.search(text)
    if not m:
        try:
            return float(text.split()[0])
        except (ValueError, IndexError):
            return None
    try:
        return float(m.group(1)) * 10000
    except ValueError:
        return None


class ZhihuHotFetcher(BaseFetcher):
    slug = "zhihu"
    name = "知乎热榜"
    lang = "zh"
    category = "china"
    region = "cn"
    interval_sec = 15 * 60
    weight = 1.1
    home_url = "https://www.zhihu.com/hot"

    async def fetch(self) -> list[NewsItem]:
        url = (
            "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web"
            "?limit=50&desktop=true"
        )
        headers: dict[str, str] = {}
        cookie = content_collector_settings.zhihu_cookie
        if cookie:
            headers["Cookie"] = cookie

        data = await fetch_json(url, headers=headers)
        rows = (data or {}).get("data") or []

        items: list[NewsItem] = []
        for rank, row in enumerate(rows, start=1):
            target = row.get("target") or {}
            title_area = target.get("title_area") or {}
            excerpt_area = target.get("excerpt_area") or {}
            metrics_area = target.get("metrics_area") or {}
            link = (target.get("link") or {}).get("url") or ""

            title = title_area.get("text")
            if not title:
                continue

            q_id_match = re.search(r"(\d+)$", link)
            ext_id = q_id_match.group(1) if q_id_match else link
            url_out = (
                f"https://www.zhihu.com/question/{ext_id}"
                if q_id_match
                else link or f"https://www.zhihu.com"
            )

            items.append(
                NewsItem(
                    external_id=ext_id,
                    title=title,
                    url=url_out,
                    mobile_url=url_out,
                    summary=excerpt_area.get("text"),
                    hot_raw=_parse_hot(metrics_area.get("text")),
                    rank=rank,
                    metrics={"raw_text": metrics_area.get("text")},
                )
            )
        return items
