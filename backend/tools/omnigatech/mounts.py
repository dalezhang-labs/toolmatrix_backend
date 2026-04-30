"""OmnigaTech route mounting via FastAPI sub-application.

Creates a sub-app with dependency_overrides so that all reused
shopline_zendesk routers transparently use the omnigatech DB engine.
"""

from __future__ import annotations

from fastapi import FastAPI

# Original get_db dependency that the routers reference
from backend.tools.shopline_zendesk.routes.zendesk.app.database import get_db

# OmnigaTech DB dependency that replaces it
from backend.tools.omnigatech.database import get_omnigatech_db

# Existing routers from shopline_zendesk
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    tenants,
    customers,
    orders,
    logistics,
    stripe_subscriptions,
    site_users,
    custom_invoice,
    subscriptions,
)

# OmnigaTech-specific routers
from backend.tools.omnigatech.routers import health

# ---------------------------------------------------------------------------
# Sub-application
# ---------------------------------------------------------------------------
omnigatech_app = FastAPI(title="OmnigaTech API")

# Override the DB dependency so every router uses the omnigatech engine
omnigatech_app.dependency_overrides[get_db] = get_omnigatech_db

# Mount all reused routers with their correct prefixes
omnigatech_app.include_router(tenants.router, prefix="/tenants", tags=["omnigatech-tenants"])
omnigatech_app.include_router(customers.router, prefix="/customers", tags=["omnigatech-customers"])
omnigatech_app.include_router(orders.router, prefix="/orders", tags=["omnigatech-orders"])
omnigatech_app.include_router(logistics.router, prefix="/logistics", tags=["omnigatech-logistics"])
omnigatech_app.include_router(stripe_subscriptions.router, prefix="/stripe", tags=["omnigatech-stripe"])
omnigatech_app.include_router(site_users.router, prefix="/users", tags=["omnigatech-users"])
omnigatech_app.include_router(custom_invoice.router, prefix="/custom-invoice", tags=["omnigatech-invoice"])
omnigatech_app.include_router(subscriptions.router, prefix="/subscriptions", tags=["omnigatech-subscriptions"])

# OmnigaTech-specific health check
omnigatech_app.include_router(health.router, tags=["omnigatech-health"])


# ---------------------------------------------------------------------------
# Public helper called from main.py
# ---------------------------------------------------------------------------
def include_omnigatech_routes(app: FastAPI) -> None:
    """Mount the OmnigaTech sub-application on the main app."""
    app.mount("/api/omnigatech", omnigatech_app)
