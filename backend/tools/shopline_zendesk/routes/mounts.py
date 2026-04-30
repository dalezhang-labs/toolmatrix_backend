"""Route mounting helpers for Shopline-Zendesk frontends.

This module keeps route registration grouped by frontend:
- Shopline App frontend (Next.js): /api/shopline-zendesk/shopline/*
- Zendesk ZAF frontend (React): legacy and v2 API groups
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    customers as zaf_customers_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    logistics as zaf_logistics_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    orders as zaf_orders_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    site_users as zaf_users_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    stripe_subscriptions as zaf_stripe_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    subscriptions as zaf_subscriptions_v2,
)
from backend.tools.shopline_zendesk.routes.zendesk.app.routers import (
    tenants as zaf_tenants_v2,
)
from backend.tools.shopline_zendesk.routes.shopline import binding as shopline_binding
from backend.tools.shopline_zendesk.routes.shopline import customers as shopline_customers
from backend.tools.shopline_zendesk.routes.shopline import install as shopline_install
from backend.tools.shopline_zendesk.routes.shopline import session as shopline_session
from backend.tools.shopline_zendesk.routes.shopline import webhook as shopline_webhook
from backend.tools.shopline_zendesk.routes.zendesk import customer as zaf_legacy_customer


SHOPLINE_FRONTEND_PREFIX = "/api/shopline-zendesk/shopline"
ZAF_LEGACY_PREFIX = "/api/shopline-zendesk/zendesk"


def include_shopline_frontend_routes(app: FastAPI) -> None:
    """Register Shopline App frontend routes."""
    app.include_router(
        shopline_install.router,
        prefix=SHOPLINE_FRONTEND_PREFIX,
        tags=["shopline-frontend"],
    )
    app.include_router(
        shopline_binding.router,
        prefix=SHOPLINE_FRONTEND_PREFIX,
        tags=["shopline-frontend"],
    )
    app.include_router(
        shopline_session.router,
        prefix=SHOPLINE_FRONTEND_PREFIX,
        tags=["shopline-frontend"],
    )
    app.include_router(
        shopline_webhook.router,
        prefix=SHOPLINE_FRONTEND_PREFIX,
        tags=["shopline-frontend"],
    )
    app.include_router(
        shopline_customers.router,
        prefix=SHOPLINE_FRONTEND_PREFIX,
        tags=["shopline-frontend"],
    )


def include_zaf_frontend_routes(app: FastAPI) -> None:
    """Register Zendesk ZAF frontend routes."""
    # Legacy Zendesk bridge route (API-key based lookup).
    app.include_router(
        zaf_legacy_customer.router,
        prefix=ZAF_LEGACY_PREFIX,
        tags=["zendesk-zaf-legacy"],
    )

    # V2 routes used by the migrated ZAF frontend.
    app.include_router(
        zaf_customers_v2.router,
        prefix="/api/customers",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_orders_v2.router,
        prefix="/api/orders",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_logistics_v2.router,
        prefix="/api/logistics",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_subscriptions_v2.router,
        prefix="/api/subscriptions",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_tenants_v2.router,
        prefix="/api/tenants",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_users_v2.router,
        prefix="/api/users",
        tags=["zendesk-zaf-v2"],
    )
    app.include_router(
        zaf_stripe_v2.router,
        prefix="/api/stripe",
        tags=["zendesk-zaf-v2"],
    )
