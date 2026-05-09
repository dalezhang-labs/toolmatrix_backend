"""Growth / psychology / philosophy blogs — fills the 'growth' category which
is mostly empty from the other sources."""

from __future__ import annotations

from ..rss_base import RSSFetcher


class AstralCodexTen(RSSFetcher):
    slug = "astral_codex_ten"
    name = "Astral Codex Ten"
    lang = "en"
    category = "world"  # rough; classifier will decide growth
    region = "global"
    interval_sec = 12 * 60 * 60  # Scott posts ~4×/week
    weight = 1.3
    feed_url = "https://astralcodexten.substack.com/feed"
    home_url = "https://astralcodexten.substack.com"
    strip_source_suffix = False


class FarnamStreet(RSSFetcher):
    slug = "farnam_street"
    name = "Farnam Street"
    lang = "en"
    category = "world"
    region = "global"
    interval_sec = 12 * 60 * 60
    weight = 1.2
    feed_url = "https://fs.blog/feed/"
    home_url = "https://fs.blog"
    strip_source_suffix = False
