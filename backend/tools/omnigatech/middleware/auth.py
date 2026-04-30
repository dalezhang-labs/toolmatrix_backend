from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class OmnigaTechAuthMiddleware(BaseHTTPMiddleware):
    """Auth middleware scoped to /api/omnigatech/ paths only."""

    PREFIX = "/api/omnigatech/"

    async def dispatch(self, request: Request, call_next):
        # Pass through requests that are not for OmnigaTech
        if not request.url.path.startswith(self.PREFIX):
            return await call_next(request)

        # Skip auth for health check
        if request.url.path == "/api/omnigatech/health":
            return await call_next(request)

        # Extract Zendesk token from header
        zendesk_token = request.headers.get("X-Zendesk-Token")
        if not zendesk_token:
            logger.debug(
                f"No Zendesk token for {request.url.path}, allowing in development mode"
            )

        # Attach token to request state
        request.state.zendesk_token = zendesk_token

        response = await call_next(request)
        return response
