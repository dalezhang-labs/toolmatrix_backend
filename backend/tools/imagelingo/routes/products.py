"""Product browsing routes — fetch products and images from Shopline API."""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Query

from backend.db.connection import get_connection
from backend.tools.imagelingo.services.token_store import get_token

logger = logging.getLogger(__name__)

router = APIRouter()

SHOPLINE_API_VERSION = "v20260901"


def _get_store_info(handle: str) -> tuple[str, str]:
    """Get store handle and access token. Falls back to first store if handle is empty."""
    if not handle:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT handle FROM imagelingo.stores ORDER BY updated_at DESC LIMIT 1")
                row = cur.fetchone()
        if row:
            handle = row[0]
    if not handle:
        raise HTTPException(404, "No store found")
    token = get_token(handle)
    if not token:
        raise HTTPException(401, "Store not authenticated or token expired")
    return handle, token


def _shopline_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


@router.get("/list")
async def list_products(
    store_handle: str = "",
    limit: int = Query(default=20, ge=1, le=50),
    page_info: str = "",
    status: str = "active",
):
    """Fetch products from Shopline with cover images."""
    handle, token = _get_store_info(store_handle)

    url = f"https://{handle}.myshopline.com/admin/openapi/{SHOPLINE_API_VERSION}/products/products.json"
    params: dict = {
        "limit": limit,
        "status": status,
        "fields": "id,title,handle,status,image,images",
    }
    if page_info:
        params["page_info"] = page_info

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=_shopline_headers(token))

    if resp.status_code == 401:
        raise HTTPException(401, "Shopline token expired")
    if resp.status_code != 200:
        logger.error("Shopline products API error (%d): %s", resp.status_code, resp.text[:200])
        raise HTTPException(502, f"Shopline API error ({resp.status_code})")

    data = resp.json()
    products = data.get("products", [])

    # Extract next page_info from Link header
    next_page = ""
    link_header = resp.headers.get("link", "")
    if 'rel="next"' in link_header:
        import re
        match = re.search(r'page_info=([^&>]+)', link_header)
        if match:
            next_page = match.group(1)

    # Simplify response for frontend
    items = []
    for p in products:
        cover = p.get("image", {})
        images = p.get("images", [])
        items.append({
            "id": p.get("id"),
            "title": p.get("title", ""),
            "handle": p.get("handle", ""),
            "status": p.get("status", ""),
            "cover_url": cover.get("src", "") if cover else "",
            "image_count": len(images),
            "images": [
                {"id": img.get("id"), "url": img.get("src", ""), "alt": img.get("alt", "")}
                for img in images
            ],
        })

    return {"products": items, "next_page": next_page}
