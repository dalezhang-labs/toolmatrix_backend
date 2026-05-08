"""Shared HTTP client for all fetchers.

Wraps httpx.AsyncClient with sensible defaults (UA, timeout, retry-on-network).
Inspired by newsnow's myFetch but translated to Python.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from ..config import content_collector_settings as _s

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {"User-Agent": _s.http_user_agent}


async def fetch_text(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
    retries: int = 2,
) -> str:
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout or _s.http_timeout_sec, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers=merged, params=params)
                resp.raise_for_status()
                return resp.text
        except (httpx.HTTPError, httpx.TransportError) as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


async def fetch_json(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
    retries: int = 2,
) -> Any:
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout or _s.http_timeout_sec, follow_redirects=True
            ) as client:
                resp = await client.request(
                    method, url, headers=merged, params=params, json=json_body
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, httpx.TransportError) as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


async def fetch_response_cookies(url: str) -> dict[str, str]:
    """Visit a URL just to collect Set-Cookie values (used by Douyin-style flows)."""
    async with httpx.AsyncClient(
        timeout=_s.http_timeout_sec, follow_redirects=True
    ) as client:
        resp = await client.get(url, headers=_DEFAULT_HEADERS)
        return {c.name: c.value for c in resp.cookies.jar}
