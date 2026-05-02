"""Tenant middleware: resolves Zendesk subdomain → Shopline credentials.

Queries shopline_zendesk.bindings + shopline_zendesk.stores to inject
shopline_domain and shopline_access_token into request.state for
downstream routers (customers, orders, logistics, etc.).
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from backend.db.connection import get_connection

logger = logging.getLogger(__name__)

# Paths that require tenant resolution
_MANAGED_PREFIXES = (
    "/api/customers",
    "/api/orders",
    "/api/logistics",
    "/api/subscriptions",
    "/api/tenants",
    "/api/users",
    "/api/stripe",
)

# Paths that should be skipped entirely (exact match)
_EXACT_SKIP = frozenset([
    "/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico",
])

# Paths that should be skipped (prefix match)
_PREFIX_SKIP = (
    "/api/subscriptions/tiers",
    "/api/users/",
    "/api/stripe/",
    "/api/tenants/by-subdomain/",
    "/api/tenants/validate-shopline-config",
    "/api/tenants/setup-config",
)


def _lookup_tenant(zendesk_subdomain: str) -> dict | None:
    """Query shopline_zendesk.bindings JOIN stores by Zendesk subdomain.

    Returns a dict with handle, shopline_domain (=handle), access_token,
    token_invalid, or None if no binding exists.
    """
    sql = """
        SELECT s.handle,
               s.access_token,
               s.token_invalid,
               b.id AS binding_id
        FROM shopline_zendesk.bindings b
        JOIN shopline_zendesk.stores s ON s.id = b.store_id
        WHERE b.zendesk_subdomain = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (zendesk_subdomain,))
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "handle": row[0],
        "access_token": row[1],
        "token_invalid": row[2],
        "binding_id": str(row[3]),
    }


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Only process managed API prefixes
        if not request.url.path.startswith(_MANAGED_PREFIXES):
            return await call_next(request)

        # Check skip lists
        should_skip = (
            request.url.path in _EXACT_SKIP
            or any(request.url.path.startswith(p) for p in _PREFIX_SKIP)
        )
        # /api/tenants/config/{subdomain} must NOT be skipped (ZAF needs it)
        if request.url.path.startswith("/api/tenants/config/"):
            should_skip = False

        if should_skip:
            return await call_next(request)

        # Resolve Zendesk subdomain
        zendesk_subdomain = request.headers.get("X-Zendesk-Subdomain")
        if not zendesk_subdomain:
            logger.warning("Missing X-Zendesk-Subdomain for %s", request.url.path)
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "Zendesk subdomain not found in request headers.",
                        "code": "ZENDESK_SUBDOMAIN_MISSING",
                    },
                )

        # Look up tenant config from shopline_zendesk schema
        try:
            tenant = _lookup_tenant(zendesk_subdomain)
        except Exception as e:
            logger.error("Tenant lookup failed for %s: %s", zendesk_subdomain, e)
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Failed to load tenant configuration",
                        "code": "TENANT_CONFIG_ERROR",
                    },
                )
            return await call_next(request)

        if not tenant:
            logger.warning("No binding found for subdomain: %s", zendesk_subdomain)
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": f"No configuration found for Zendesk subdomain: {zendesk_subdomain}",
                        "code": "TENANT_CONFIG_NOT_FOUND",
                    },
                )
        else:
            # Inject into request.state for downstream routers
            request.state.shopline_domain = tenant["handle"]
            request.state.shopline_access_token = tenant["access_token"]
            request.state.zendesk_subdomain = zendesk_subdomain
            request.state.tenant_handle = tenant["handle"]
            request.state.token_invalid = tenant["token_invalid"]
            logger.info(
                "Tenant resolved: %s → %s (token_invalid=%s)",
                zendesk_subdomain,
                tenant["handle"],
                tenant["token_invalid"],
            )

        return await call_next(request)
