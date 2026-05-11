"""Request guard for paid endpoints — HMAC signature verification + rate limiting.

Security layers for the translate endpoint:
1. HMAC signature: frontend signs each request with a session token, backend verifies.
   This prevents unauthorized direct API calls even if someone knows a store_handle.
2. Rate limiting: per-store and per-IP limits to prevent abuse.
3. Timestamp validation: reject requests older than 5 minutes (anti-replay).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────

# Secret used to generate session tokens for stores
# In production, this should be a strong random value in env vars
SIGNING_SECRET = os.environ.get("IMAGELINGO_SIGNING_SECRET", "")

# Rate limit: max requests per window
RATE_LIMIT_PER_STORE = int(os.environ.get("IMAGELINGO_RATE_LIMIT_STORE", "30"))  # per store per window
RATE_LIMIT_PER_IP = int(os.environ.get("IMAGELINGO_RATE_LIMIT_IP", "60"))  # per IP per window
RATE_LIMIT_WINDOW = int(os.environ.get("IMAGELINGO_RATE_LIMIT_WINDOW", "300"))  # 5 minutes

# Timestamp tolerance for anti-replay (seconds)
TIMESTAMP_TOLERANCE = 300  # 5 minutes


# ── HMAC Signature ───────────────────────────────────────────────────────

def generate_session_token(store_handle: str) -> str:
    """Generate a session token for a store. Called after successful OAuth.
    The token is HMAC(store_handle + app_secret_suffix, signing_secret).
    This token is sent to the frontend and used to sign requests.
    """
    if not SIGNING_SECRET:
        # Fallback: use SHOPLINE_APP_SECRET as signing key
        secret = os.environ.get("SHOPLINE_APP_SECRET", "fallback-dev-secret")
    else:
        secret = SIGNING_SECRET

    payload = f"{store_handle}:imagelingo-session"
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_request_signature(
    store_handle: str,
    timestamp: str,
    signature: str,
    body: str = "",
) -> bool:
    """Verify the HMAC signature on a request.

    Signature = HMAC-SHA256(store_handle + timestamp + body_hash, session_token)

    Args:
        store_handle: the store making the request
        timestamp: Unix timestamp (ms) from X-Timestamp header
        signature: the signature from X-Signature header
        body: request body string (for POST requests)
    """
    if not signature or not timestamp:
        return False

    # Validate timestamp freshness (anti-replay)
    try:
        req_time = int(timestamp) / 1000  # ms to seconds
        now = time.time()
        if abs(now - req_time) > TIMESTAMP_TOLERANCE:
            logger.warning("Request timestamp too old: %s (now=%d, diff=%ds)",
                          timestamp, int(now), int(abs(now - req_time)))
            return False
    except (ValueError, TypeError):
        return False

    # Compute expected signature
    session_token = generate_session_token(store_handle)
    body_hash = hashlib.sha256(body.encode()).hexdigest() if body else ""
    message = f"{store_handle}:{timestamp}:{body_hash}"

    expected = hmac.new(
        session_token.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ── Rate Limiting (in-memory, suitable for single-instance Railway) ──────

class RateLimiter:
    """Simple sliding window rate limiter using in-memory storage.
    For a single Railway instance this is sufficient.
    If you scale to multiple instances, switch to Redis.
    """

    def __init__(self):
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check if request is allowed.
        Returns (allowed, remaining_requests).
        """
        now = time.time()
        cutoff = now - window

        with self._lock:
            # Clean old entries
            self._store[key] = [t for t in self._store[key] if t > cutoff]
            current = len(self._store[key])

            if current >= limit:
                return False, 0

            self._store[key].append(now)
            return True, limit - current - 1

    def cleanup(self):
        """Remove expired entries to prevent memory leak."""
        now = time.time()
        max_window = RATE_LIMIT_WINDOW * 2  # generous cleanup window

        with self._lock:
            expired_keys = [
                k for k, v in self._store.items()
                if not v or v[-1] < now - max_window
            ]
            for k in expired_keys:
                del self._store[k]


# Global rate limiter instance
_limiter = RateLimiter()


def check_rate_limit(store_handle: str, client_ip: str) -> None:
    """Check both store-level and IP-level rate limits.
    Raises HTTPException(429) if either limit is exceeded.
    """
    # Store-level limit
    store_key = f"store:{store_handle}"
    allowed, remaining = _limiter.is_allowed(store_key, RATE_LIMIT_PER_STORE, RATE_LIMIT_WINDOW)
    if not allowed:
        logger.warning("Rate limit exceeded for store %s", store_handle)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a few minutes before trying again.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    # IP-level limit
    ip_key = f"ip:{client_ip}"
    allowed, remaining = _limiter.is_allowed(ip_key, RATE_LIMIT_PER_IP, RATE_LIMIT_WINDOW)
    if not allowed:
        logger.warning("Rate limit exceeded for IP %s", client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many requests from this address. Please wait.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )


# ── Combined guard for paid endpoints ───────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting proxy headers."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def guard_paid_endpoint(request: Request, store_handle: str) -> None:
    """Combined security check for paid endpoints (translate).
    Call this at the start of any endpoint that costs credits.

    Checks:
    1. Rate limiting (always enforced)
    2. HMAC signature (enforced when IMAGELINGO_SIGNING_SECRET is set)
    """
    client_ip = get_client_ip(request)

    # Rate limiting — always active
    check_rate_limit(store_handle, client_ip)

    # HMAC signature — only enforced when signing secret is configured
    # This allows gradual rollout: set the env var when ready
    if not SIGNING_SECRET:
        return  # Skip signature check in dev / before frontend is updated

    signature = request.headers.get("x-signature", "")
    timestamp = request.headers.get("x-timestamp", "")

    if not signature or not timestamp:
        logger.warning("Missing signature headers from IP %s for store %s", client_ip, store_handle)
        raise HTTPException(401, "Missing request signature. Please refresh the page.")

    # For POST requests, include body in signature
    body = ""
    if request.method == "POST":
        body = (await request.body()).decode("utf-8", errors="replace")

    if not verify_request_signature(store_handle, timestamp, signature, body):
        logger.warning("Invalid signature from IP %s for store %s", client_ip, store_handle)
        raise HTTPException(403, "Invalid request signature. Please refresh the page and try again.")
