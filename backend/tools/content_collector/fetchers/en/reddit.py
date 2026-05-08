"""Reddit — hot posts from selected subreddits.

Reddit rate-limits anonymous traffic aggressively and outright 403s many cloud
IP ranges (Railway/Heroku/Vercel). Two modes:

1. OAuth2 app-only (preferred, stable): set REDDIT_CLIENT_ID/SECRET in env.
   We grab a token from /api/v1/access_token and call oauth.reddit.com.
   Free, 60 req/min per OAuth client. Recommended for any self-hosted deploy.

2. Anonymous (fallback): old.reddit.com/.json with a desktop UA. Works from
   residential IPs but gets 403'd from many datacenters.

Register an app (2 min): https://www.reddit.com/prefs/apps → "script" type.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from datetime import datetime, timezone

from ..base import BaseFetcher, NewsItem
from ..http import fetch_json


_UA = (
    "content-collector/0.1 (by /u/dalezhang_labs; +https://github.com/dalezhang-labs)"
)

# ---------- OAuth2 token cache (process-local) ----------
_token_cache: dict[str, float | str] = {"token": "", "expires_at": 0.0}
_token_lock = asyncio.Lock()


async def _get_oauth_token() -> str | None:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None

    now = time.time()
    if _token_cache["token"] and float(_token_cache["expires_at"]) - 60 > now:
        return str(_token_cache["token"])

    async with _token_lock:
        # Re-check inside the lock
        if _token_cache["token"] and float(_token_cache["expires_at"]) - 60 > now:
            return str(_token_cache["token"])

        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        data = await fetch_json(
            "https://www.reddit.com/api/v1/access_token",
            method="POST",
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": _UA,
            },
            # We use `params` for form-encoded body via httpx only for GET;
            # for POST we need to pass it as raw form. Fall back to a tiny
            # helper below because fetch_json is JSON-only.
        )
        # The above will fail because fetch_json sends JSON; handle via httpx.
        raise RuntimeError("unreachable")  # pragma: no cover


# ---------- Direct httpx for token (form-encoded) ----------
async def _fetch_oauth_token_httpx() -> str | None:
    import httpx

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None

    now = time.time()
    if _token_cache["token"] and float(_token_cache["expires_at"]) - 60 > now:
        return str(_token_cache["token"])

    async with _token_lock:
        if _token_cache["token"] and float(_token_cache["expires_at"]) - 60 > now:
            return str(_token_cache["token"])

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"User-Agent": _UA},
            )
            resp.raise_for_status()
            payload = resp.json()
            token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))
            if not token:
                return None
            _token_cache["token"] = token
            _token_cache["expires_at"] = now + expires_in
            return token


async def _fetch_subreddit(subreddit: str) -> list[dict]:
    """Returns raw children[].data list via OAuth2 if available, else anon."""
    token = await _fetch_oauth_token_httpx()
    if token:
        url = f"https://oauth.reddit.com/r/{subreddit}/hot?limit=25"
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": _UA,
        }
    else:
        url = f"https://old.reddit.com/r/{subreddit}/hot.json?limit=25"
        headers = {"User-Agent": _UA}

    data = await fetch_json(url, headers=headers)
    return ((data or {}).get("data") or {}).get("children") or []


class _RedditBase(BaseFetcher):
    subreddit: str = ""

    lang = "en"
    category = "tech"
    region = "global"
    interval_sec = 60 * 60
    weight = 1.0
    fetcher_type = "native"

    async def fetch(self) -> list[NewsItem]:
        children = await _fetch_subreddit(self.subreddit)

        items: list[NewsItem] = []
        for rank, ch in enumerate(children, start=1):
            d = ch.get("data") or {}
            if d.get("stickied"):
                continue
            rid = d.get("id")
            title = d.get("title")
            if not (rid and title):
                continue

            score = d.get("score")
            num_comments = d.get("num_comments", 0)
            permalink = d.get("permalink") or f"/r/{self.subreddit}/comments/{rid}"
            url_ext = d.get("url") or f"https://www.reddit.com{permalink}"
            created_utc = d.get("created_utc")

            items.append(
                NewsItem(
                    external_id=rid,
                    title=title,
                    url=url_ext,
                    mobile_url=f"https://www.reddit.com{permalink}",
                    author=d.get("author"),
                    summary=d.get("selftext") or None,
                    published_at=(
                        datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if created_utc
                        else None
                    ),
                    hot_raw=float(score) if isinstance(score, (int, float)) else None,
                    rank=rank,
                    metrics={
                        "upvotes": score,
                        "comments": num_comments,
                        "upvote_ratio": d.get("upvote_ratio"),
                    },
                )
            )
        return items


class RedditProgramming(_RedditBase):
    slug = "reddit_programming"
    name = "Reddit r/programming"
    subreddit = "programming"
    home_url = "https://www.reddit.com/r/programming/"


class RedditTechnology(_RedditBase):
    slug = "reddit_technology"
    name = "Reddit r/technology"
    subreddit = "technology"
    home_url = "https://www.reddit.com/r/technology/"


class RedditStartups(_RedditBase):
    slug = "reddit_startups"
    name = "Reddit r/startups"
    subreddit = "startups"
    interval_sec = 2 * 60 * 60
    home_url = "https://www.reddit.com/r/startups/"
