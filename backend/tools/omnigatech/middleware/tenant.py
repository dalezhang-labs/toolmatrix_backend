from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.tools.shopline_zendesk.routes.zendesk.app.models.base import TenantModel
from ..database import get_omnigatech_sync_db
import logging

logger = logging.getLogger(__name__)


class OmnigaTechTenantMiddleware(BaseHTTPMiddleware):
    """Tenant resolution middleware scoped to /api/omnigatech/ paths only."""

    PREFIX = "/api/omnigatech/"

    # Paths that do not require tenant resolution
    SKIP_PREFIXES = (
        "/api/omnigatech/users/",
        "/api/omnigatech/stripe/",
        "/api/omnigatech/health",
    )

    async def dispatch(self, request: Request, call_next):
        # Pass through requests that are not for OmnigaTech
        if not request.url.path.startswith(self.PREFIX):
            return await call_next(request)

        # Skip CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip paths that don't need tenant
        if any(request.url.path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        # Read subdomain header
        zendesk_subdomain = request.headers.get("X-Zendesk-Subdomain")
        if not zendesk_subdomain:
            logger.warning(
                f"Missing X-Zendesk-Subdomain header for {request.url.path}"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Zendesk subdomain not found in request headers.",
                    "code": "ZENDESK_SUBDOMAIN_MISSING",
                },
            )

        # Query tenant from omnigatech DB
        db: Session | None = None
        try:
            db_gen = get_omnigatech_sync_db()
            db = next(db_gen)

            tenant_config = (
                db.query(TenantModel)
                .filter(
                    TenantModel.zendesk_subdomain == zendesk_subdomain,
                    TenantModel.is_active == True,  # noqa: E712
                )
                .first()
            )

            if not tenant_config:
                logger.warning(
                    f"No active tenant for subdomain: {zendesk_subdomain}"
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": f"No configuration found for Zendesk subdomain: {zendesk_subdomain}",
                        "code": "TENANT_CONFIG_NOT_FOUND",
                    },
                )

            # Attach tenant info to request state
            request.state.shopline_domain = tenant_config.shopline_domain
            request.state.shopline_access_token = tenant_config.shopline_access_token
            request.state.zendesk_subdomain = zendesk_subdomain
            request.state.tenant_id = tenant_config.id

            logger.info(
                f"OmnigaTech tenant resolved: {zendesk_subdomain} -> "
                f"domain={tenant_config.shopline_domain}"
            )

        except Exception as e:
            logger.error(f"Error loading OmnigaTech tenant configuration: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Failed to load tenant configuration",
                    "code": "TENANT_CONFIG_ERROR",
                },
            )
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

        response = await call_next(request)
        return response
