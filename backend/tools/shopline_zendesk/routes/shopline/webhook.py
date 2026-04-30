"""GDPR webhook routes for Shopline-Zendesk integration."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Request

from backend.db.connection import get_connection

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_webhook(body: bytes, signature: str) -> bool:
    """Verify Shopline webhook HMAC-SHA256 signature."""
    secret = os.getenv("SHOPLINE_ZD_APP_SECRET", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# GDPR: Customer data erasure
# ---------------------------------------------------------------------------


@router.post("/gdpr/customers-data-erasure")
async def customers_data_erasure(
    request: Request,
    x_shopline_hmac_sha256: str = Header(default=""),
):
    """GDPR customer data erasure request.

    shopline-zendesk does not store any customer PII — we only store
    Shopline OAuth tokens and Zendesk binding config. Acknowledge and return OK.
    """
    body = await request.body()
    if x_shopline_hmac_sha256 and not _verify_webhook(body, x_shopline_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    logger.info("GDPR customers-data-erasure received (no PII stored)")
    return {"status": "ok", "message": "No customer data stored"}


# ---------------------------------------------------------------------------
# GDPR: Shop data erasure (merchant uninstall)
# ---------------------------------------------------------------------------


@router.post("/gdpr/shop-data-erasure")
async def shop_data_erasure(
    request: Request,
    x_shopline_hmac_sha256: str = Header(default=""),
):
    """GDPR shop data erasure request.

    When a merchant uninstalls the app, delete their store token and
    Zendesk binding from the database (cascade: bindings → stores).
    """
    body = await request.body()
    if x_shopline_hmac_sha256 and not _verify_webhook(body, x_shopline_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    # Shopline sends domain as e.g. "mystore.myshopline.com"
    domain = payload.get("domain", "")
    handle = domain.replace(".myshopline.com", "").strip()

    if handle:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM shopline_zendesk.stores WHERE handle = %s",
                    (handle,),
                )
                row = cur.fetchone()
                if row:
                    store_id = str(row[0])
                    # Delete binding first (FK constraint)
                    cur.execute(
                        "DELETE FROM shopline_zendesk.bindings WHERE store_id = %s",
                        (store_id,),
                    )
                    cur.execute(
                        "DELETE FROM shopline_zendesk.stores WHERE id = %s",
                        (store_id,),
                    )
                    logger.info("Shop data erased for handle=%s", handle)
            conn.commit()

    return {"status": "ok", "message": "Shop data erased"}
