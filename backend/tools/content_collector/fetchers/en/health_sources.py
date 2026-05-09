"""Health & medicine sources."""

from __future__ import annotations

from ..rss_base import RSSFetcher


class StatNews(RSSFetcher):
    slug = "stat_news"
    name = "STAT News"
    lang = "en"
    category = "world"
    region = "us"
    interval_sec = 4 * 60 * 60
    weight = 1.2
    feed_url = "https://www.statnews.com/feed/"
    home_url = "https://www.statnews.com"
    strip_source_suffix = False
