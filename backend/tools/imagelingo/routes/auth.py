import hashlib
import hmac
import logging
import os
import time
import urllib.parse

import httpx

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter()

SCOPES = "read_products,write_products"


def _env(key: str) -> str:
    return os.getenv(key, "")


def _make_sign(params: dict[str, str]) -> str:
    """Generate HMAC-SHA256 signature for GET request verification.
    Shopline GET sign = HMAC-SHA256(sorted query params joined by &, app_secret)
    """
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(
        _env("SHOPLINE_APP_SECRET").encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac(params: dict) -> bool:
    """Verify Shopline HMAC-SHA256 signature on incoming GET requests."""
    sign = params.get("sign", "")
    filtered = {k: v for k, v in params.items() if k != "sign"}
    expected = _make_sign(filtered)
    return hmac.compare_digest(expected, sign)


# ── App entry point (Shopline loads this URL) ────────────────────────────

@router.get("/entry")
async def app_entry(request: Request):
    """Shopline loads this URL when merchant opens the app.
    - First visit: has sign param → verify signature, check if authorized, redirect to OAuth or frontend
    - Subsequent visits: Shopline still sends sign params → verify and redirect to frontend
    """
    params = dict(request.query_params)
    handle = params.get("handle", "")

    # Verify signature
    if not verify_hmac(params):
        logger.warning("App entry signature verification failed for handle=%s", handle)
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Check if store already has a valid token
    from backend.tools.imagelingo.services.token_store import get_token
    token = get_token(handle) if handle else None

    if token:
        # Already authorized → redirect to frontend (loaded inside Shopline iframe)
        frontend_url = _env("FRONTEND_URL") or "http://localhost:3000"
        return RedirectResponse(f"{frontend_url}?shop={handle}")

    # Not authorized → break out of iframe to OAuth page
    # OAuth page is a full Shopline admin page, loading it inside the app iframe
    # causes nested sidebars. Use a small HTML page with JS to redirect top window.
    app_key = _env("SHOPLINE_APP_KEY")
    redirect_uri = urllib.parse.quote(_env("SHOPLINE_REDIRECT_URI"), safe="")
    auth_url = (
        f"https://{handle}.myshopline.com/admin/oauth-web/#/oauth/authorize"
        f"?appKey={app_key}&responseType=code&scope={SCOPES}&redirectUri={redirect_uri}"
    )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        f'<!DOCTYPE html><html><head><title>Redirecting...</title></head>'
        f'<body><script>window.top.location.href = "{auth_url}";</script>'
        f'<p>Redirecting to authorization...</p></body></html>'
    )


# ── Step 2: Verify install request and redirect to OAuth ─────────────────

@router.get("/install")
async def install(request: Request):
    """Shopline sends merchants here when they click 'Install'.
    We verify the signature, then redirect to Shopline OAuth authorization page.
    """
    params = dict(request.query_params)
    handle = params.get("handle", "")

    # Verify signature (required for production / app review)
    if not verify_hmac(params):
        logger.warning("Install request signature verification failed for handle=%s", handle)
        raise HTTPException(status_code=401, detail="Invalid signature")

    app_key = _env("SHOPLINE_APP_KEY")
    redirect_uri = urllib.parse.quote(_env("SHOPLINE_REDIRECT_URI"), safe="")
    auth_url = (
        f"https://{handle}.myshopline.com/admin/oauth-web/#/oauth/authorize"
        f"?appKey={app_key}&responseType=code&scope={SCOPES}&redirectUri={redirect_uri}"
    )
    return RedirectResponse(auth_url)


# ── Step 5-7: Receive code, verify signature, exchange for token ─────────

@router.get("/callback")
@router.get("/callback/")
async def callback(request: Request):
    """OAuth callback: Shopline redirects here with authorization code.
    We verify the signature, then exchange code for access token.
    """
    params = dict(request.query_params)
    code = params.get("code", "")
    handle = params.get("handle", "")

    if not code or not handle:
        raise HTTPException(status_code=400, detail="Missing code or handle")

    # Step 5: Verify callback signature
    if not verify_hmac(params):
        logger.warning("Callback signature verification failed for handle=%s", handle)
        raise HTTPException(status_code=401, detail="Invalid callback signature")

    # Step 6: Exchange code for access token
    app_key = _env("SHOPLINE_APP_KEY")
    app_secret = _env("SHOPLINE_APP_SECRET")
    timestamp = str(int(time.time() * 1000))

    import json as _json
    body = {"code": code}
    body_str = _json.dumps(body, separators=(",", ":"))
    # POST sign = HMAC-SHA256(body_string + timestamp, app_secret)
    source = body_str + timestamp
    sign = hmac.new(
        app_secret.encode("utf-8"),
        source.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    token_url = f"https://{handle}.myshopline.com/admin/oauth/token/create"
    headers = {
        "Content-Type": "application/json",
        "appkey": app_key,
        "timestamp": timestamp,
        "sign": sign,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, content=body_str, headers=headers)

    data = resp.json()
    logger.info("Shopline token response for %s: code=%s", handle, data.get("code"))

    if data.get("code") != 200 or not data.get("data"):
        detail = data.get("message") or data.get("i18nCode") or "Token exchange failed"
        raise HTTPException(status_code=502, detail=detail)

    # Step 7: Store access token
    token_data = data["data"]
    access_token = token_data.get("accessToken")
    expire_time = token_data.get("expireTime")
    scopes = token_data.get("scope", SCOPES)

    if not access_token:
        raise HTTPException(status_code=502, detail="No accessToken in response data")

    from datetime import datetime, timezone, timedelta
    if expire_time:
        try:
            expires_at = datetime.fromisoformat(expire_time)
        except ValueError:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=10)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=10)

    from backend.tools.imagelingo.services.token_store import save_token
    save_token(handle, access_token, expires_at, scopes)

    # Create subscription record if not exists
    from backend.db.connection import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM imagelingo.stores WHERE handle = %s", (handle,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    """INSERT INTO imagelingo.subscriptions (store_id, plan, credits_limit)
                       VALUES (%s, 'free', 200)
                       ON CONFLICT (store_id) DO NOTHING""",
                    (str(row[0]),),
                )
        conn.commit()

    frontend_url = _env("FRONTEND_URL") or "http://localhost:3000"
    # Redirect to frontend after OAuth (loaded inside Shopline iframe)
    return RedirectResponse(f"{frontend_url}?shop={handle}")


# ── Re-auth helper ───────────────────────────────────────────────────────

@router.get("/reauth-url")
async def reauth_url(handle: str = ""):
    """Return the OAuth URL for re-authentication when token expires."""
    if not handle:
        from backend.db.connection import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT handle FROM imagelingo.stores ORDER BY updated_at DESC LIMIT 1")
                row = cur.fetchone()
        if row:
            handle = row[0]
    if not handle:
        raise HTTPException(400, "No store found. Please install the app first.")
    app_key = _env("SHOPLINE_APP_KEY")
    redirect_uri = urllib.parse.quote(_env("SHOPLINE_REDIRECT_URI"), safe="")
    auth_url = (
        f"https://{handle}.myshopline.com/admin/oauth-web/#/oauth/authorize"
        f"?appKey={app_key}&responseType=code&scope={SCOPES}&redirectUri={redirect_uri}"
    )
    return {"auth_url": auth_url, "handle": handle}
