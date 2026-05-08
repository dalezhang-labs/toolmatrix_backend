"""36 氪快讯榜 — HTML parse of /newsflashes page."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..base import BaseFetcher, NewsItem
from ..http import fetch_text


class KrQuickFetcher(BaseFetcher):
    slug = "36kr"
    name = "36 氪快讯"
    lang = "zh"
    category = "china"
    region = "cn"
    interval_sec = 30 * 60
    weight = 0.9
    home_url = "https://www.36kr.com/newsflashes"

    async def fetch(self) -> list[NewsItem]:
        html = await fetch_text("https://www.36kr.com/newsflashes")
        soup = BeautifulSoup(html, "html.parser")

        items: list[NewsItem] = []
        for rank, el in enumerate(soup.select(".newsflash-item"), start=1):
            a = el.select_one("a.item-title")
            if not a:
                continue
            href = a.get("href") or ""
            title = a.get_text(strip=True)
            if not title:
                continue
            if href.startswith("/"):
                href = f"https://www.36kr.com{href}"
            items.append(
                NewsItem(
                    external_id=href,
                    title=title,
                    url=href,
                    mobile_url=href,
                    # No numeric score — ingest layer falls back to rank-based
                    rank=rank,
                )
            )
        return items
