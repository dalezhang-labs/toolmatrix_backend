"""Mainstream news outlets via RSS."""

from __future__ import annotations

from ..rss_base import RSSFetcher


class NYTTopStories(RSSFetcher):
    slug = "nyt_top"
    name = "New York Times · Top Stories"
    lang = "en"
    category = "world"
    region = "us"
    interval_sec = 60 * 60
    weight = 1.2
    feed_url = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
    home_url = "https://www.nytimes.com"
    strip_source_suffix = False


class BBCWorld(RSSFetcher):
    slug = "bbc_world"
    name = "BBC News · World"
    lang = "en"
    category = "world"
    region = "global"
    interval_sec = 60 * 60
    weight = 1.2
    feed_url = "https://feeds.bbci.co.uk/news/world/rss.xml"
    home_url = "https://www.bbc.com/news"
    strip_source_suffix = False
