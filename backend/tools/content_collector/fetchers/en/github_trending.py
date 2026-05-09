"""GitHub Trending — daily / weekly / monthly trending repos.

Parses GitHub's HTML trending page (no public API). Three fetchers cover
different time windows so the dashboard can show what's hot today, this week,
and this month.

Each item captures:
  - repo name + URL
  - description (summary)
  - total star count (hot_raw)
  - stars gained in the period (stars_gained) — the "growth" signal
  - primary programming language
  - period label (daily / weekly / monthly)
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base import BaseFetcher, NewsItem
from ..http import fetch_text

_STAR_NUM_RE = re.compile(r"[\d,]+")


def _parse_stars(text: str | None) -> float | None:
    if not text:
        return None
    m = _STAR_NUM_RE.search(text.replace(",", ""))
    return float(m.group(0)) if m else None


async def _fetch_trending(since: str, limit: int = 25) -> list[NewsItem]:
    """Shared scraper for all three time windows."""
    url = f"https://github.com/trending?since={since}&spoken_language_code="
    html = await fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")

    items: list[NewsItem] = []
    articles = soup.select("main .Box div[data-hpc] > article")
    for rank, article in enumerate(articles[:limit], start=1):
        a = article.select_one("h2 a")
        if not a:
            continue
        href = a.get("href", "").strip()
        # "/ owner / repo" → "owner/repo"
        title = " / ".join(p.strip() for p in href.strip("/").split("/")[:2])
        if not (href and title):
            continue

        # Total stars
        star_el = article.select_one('a[href$="stargazers"]')
        total_stars = _parse_stars(star_el.get_text() if star_el else None)

        # Stars gained in this period — the span that says "X stars today"
        # or "X stars this week" etc.
        gained_el = article.select_one("span.d-inline-block.float-sm-right")
        gained_text = gained_el.get_text(strip=True) if gained_el else ""
        stars_gained = _parse_stars(gained_text)

        # Primary language
        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        language = lang_el.get_text(strip=True) if lang_el else None

        # Description
        desc_el = article.select_one("p")
        desc = desc_el.get_text(strip=True) if desc_el else None

        # Build a rich summary line
        parts: list[str] = []
        if language:
            parts.append(language)
        if total_stars is not None:
            parts.append(f"⭐ {int(total_stars):,}")
        if stars_gained is not None:
            period_label = {"daily": "today", "weekly": "this week", "monthly": "this month"}.get(since, since)
            parts.append(f"+{int(stars_gained):,} {period_label}")
        meta_line = " · ".join(parts)

        full_summary = "\n".join(filter(None, [desc, meta_line])) or None

        items.append(
            NewsItem(
                external_id=f"{href}:{since}",
                title=title,
                url=f"https://github.com{href}",
                summary=full_summary,
                # Use stars_gained as hot_raw so ranking reflects growth
                # velocity, not just absolute popularity.
                hot_raw=stars_gained if stars_gained is not None else total_stars,
                rank=rank,
                metrics={
                    "total_stars": total_stars,
                    "stars_gained": stars_gained,
                    "language": language,
                    "since": since,
                },
            )
        )
    return items


class GithubTrendingDailyFetcher(BaseFetcher):
    slug = "github_trending"
    name = "GitHub Trending · Daily"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 6 * 60 * 60
    weight = 1.0
    home_url = "https://github.com/trending?since=daily"

    async def fetch(self) -> list[NewsItem]:
        return await _fetch_trending("daily")


class GithubTrendingWeeklyFetcher(BaseFetcher):
    slug = "github_trending_weekly"
    name = "GitHub Trending · Weekly"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 12 * 60 * 60  # weekly list changes slowly
    weight = 1.0
    home_url = "https://github.com/trending?since=weekly"

    async def fetch(self) -> list[NewsItem]:
        return await _fetch_trending("weekly")


class GithubTrendingMonthlyFetcher(BaseFetcher):
    slug = "github_trending_monthly"
    name = "GitHub Trending · Monthly"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 24 * 60 * 60  # monthly list barely changes day-to-day
    weight = 0.9
    home_url = "https://github.com/trending?since=monthly"

    async def fetch(self) -> list[NewsItem]:
        return await _fetch_trending("monthly")
