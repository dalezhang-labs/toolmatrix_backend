"""抖音热搜 — /aweme/v1/web/hot/search/list.

Auth trick: first GET login.douyin.com to harvest anti-bot cookies, then call
the hot-search API with them. Same approach newsnow uses — self-refreshing,
no manual cookie maintenance.
"""

from __future__ import annotations

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json, fetch_response_cookies


class DouyinHotFetcher(BaseFetcher):
    slug = "douyin"
    name = "抖音热搜"
    lang = "zh"
    category = "china"
    region = "cn"
    interval_sec = 30 * 60
    weight = 1.1
    home_url = "https://www.douyin.com/hot"

    async def fetch(self) -> list[NewsItem]:
        cookies = await fetch_response_cookies("https://login.douyin.com/")
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

        url = (
            "https://www.douyin.com/aweme/v1/web/hot/search/list/"
            "?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
        )
        data = await fetch_json(url, headers={"Cookie": cookie_header})
        rows = ((data or {}).get("data") or {}).get("word_list") or []

        items: list[NewsItem] = []
        for rank, r in enumerate(rows, start=1):
            sid = r.get("sentence_id")
            word = r.get("word")
            if not (sid and word):
                continue
            hot = r.get("hot_value")
            try:
                hot_val = float(hot) if hot is not None else None
            except (TypeError, ValueError):
                hot_val = None
            items.append(
                NewsItem(
                    external_id=sid,
                    title=word,
                    url=f"https://www.douyin.com/hot/{sid}",
                    mobile_url=f"https://www.douyin.com/hot/{sid}",
                    hot_raw=hot_val,
                    rank=rank,
                    metrics={"hot_value": hot},
                    extra={"event_time": r.get("event_time")},
                )
            )
        return items
