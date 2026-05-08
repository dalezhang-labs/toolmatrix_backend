"""GitHub Trending — daily trending repos. Parses HTML because GitHub has no
public trending API. Matches newsnow's selectors."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..base import BaseFetcher, NewsItem
from ..http import fetch_text


class GithubTrendingFetcher(BaseFetcher):
    slug = "github_trending"
    name = "GitHub Trending"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 6 * 60 * 60
    weight = 1.0
    home_url = "https://github.com/trending"

    async def fetch(self) -> list[NewsItem]:
        html = await fetch_text("https://github.com/trending?spoken_language_code=")
        soup = BeautifulSoup(html, "html.parser")

        items: list[NewsItem] = []
        articles = soup.select("main .Box div[data-hpc] > article")
        for rank, article in enumerate(articles, start=1):
            a = article.select_one("h2 a")
            if not a:
                continue
            href = a.get("href", "").strip()
            title = " ".join(a.get_text(strip=True).split())
            if not (href and title):
                continue

            star_el = article.select_one('a[href$="stargazers"]')
            star_text = (
                "".join(star_el.get_text().split()) if star_el else ""
            )
            try:
                # Strip commas ("1,234") to get a raw number for hot_raw
                star_num = float(star_text.replace(",", "")) if star_text else None
            except ValueError:
                star_num = None

            desc_el = article.select_one("p")
            desc = desc_el.get_text(strip=True) if desc_el else None

            items.append(
                NewsItem(
                    external_id=href,
                    title=title,
                    url=f"https://github.com{href}",
                    summary=desc,
                    hot_raw=star_num,
                    rank=rank,
                    metrics={"stars_today": star_text} if star_text else {},
                )
            )
        return items
