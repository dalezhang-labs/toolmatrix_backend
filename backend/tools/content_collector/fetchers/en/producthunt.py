"""Product Hunt — top posts via their GraphQL API.

Requires PRODUCTHUNT_API_TOKEN (free, register at api.producthunt.com/v2/docs).
If the token isn't configured, fetch() raises so the source is marked errored
and the dashboard will show a red pill.
"""

from __future__ import annotations

from ...config import content_collector_settings
from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


_GQL = """
query {
  posts(first: 30, order: VOTES) {
    edges {
      node {
        id
        name
        tagline
        votesCount
        url
        slug
      }
    }
  }
}
"""


class ProductHuntFetcher(BaseFetcher):
    slug = "producthunt"
    name = "Product Hunt"
    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 60 * 60
    weight = 1.0
    home_url = "https://www.producthunt.com/"

    async def fetch(self) -> list[NewsItem]:
        token = content_collector_settings.producthunt_token
        if not token:
            raise RuntimeError(
                "PRODUCTHUNT_API_TOKEN not set — skipping Product Hunt"
            )

        data = await fetch_json(
            "https://api.producthunt.com/v2/api/graphql",
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json_body={"query": _GQL},
        )
        posts = ((data or {}).get("data") or {}).get("posts", {}).get("edges", [])

        items: list[NewsItem] = []
        for rank, edge in enumerate(posts, start=1):
            n = edge.get("node") or {}
            pid = n.get("id")
            name = n.get("name")
            if not (pid and name):
                continue
            items.append(
                NewsItem(
                    external_id=pid,
                    title=name,
                    url=n.get("url") or f"https://www.producthunt.com/posts/{n.get('slug')}",
                    summary=n.get("tagline"),
                    hot_raw=float(n.get("votesCount") or 0),
                    rank=rank,
                    metrics={"votes": n.get("votesCount")},
                )
            )
        return items
