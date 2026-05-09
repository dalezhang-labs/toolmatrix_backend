"""Google News — top stories / topic feeds / search queries via RSS.

Three sources:
  - gnews_us_top     US headlines (→ news)
  - gnews_tech       Technology topic (→ knowledge)
  - gnews_ai_search  'AI' search query (→ knowledge)

Google News RSS carries no engagement data; ingest falls back to rank-based
scoring (first item = hottest). The `<source>` tag per item is stripped from
the headline (e.g. "...  - NYT") and kept as metadata for display.
"""

from __future__ import annotations

from ..rss_base import RSSFetcher


class GoogleNewsUSTop(RSSFetcher):
    slug = "gnews_us_top"
    name = "Google News · US 头条"
    lang = "en"
    category = "world"
    region = "us"
    interval_sec = 60 * 60
    weight = 1.1
    feed_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    home_url = "https://news.google.com"


class GoogleNewsTech(RSSFetcher):
    slug = "gnews_tech"
    name = "Google News · Technology"
    lang = "en"
    category = "tech"
    region = "us"
    interval_sec = 60 * 60
    weight = 1.0
    # Stable topic id for "Technology" on Google News EN-US.
    feed_url = (
        "https://news.google.com/rss/topics/"
        "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB"
        "?hl=en-US&gl=US&ceid=US:en"
    )
    home_url = "https://news.google.com"


class GoogleNewsAISearch(RSSFetcher):
    slug = "gnews_ai_search"
    name = "Google News · AI"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 60 * 60
    weight = 1.2
    feed_url = (
        "https://news.google.com/rss/search"
        "?q=AI+OR+LLM+OR+OpenAI+OR+Anthropic+OR+%22artificial+intelligence%22"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    home_url = "https://news.google.com"
