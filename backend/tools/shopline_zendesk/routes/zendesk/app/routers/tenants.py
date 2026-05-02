"""Tenant configuration routes for the ZAF app.

All queries go through shopline_zendesk.stores + shopline_zendesk.bindings
via the shared psycopg2 connection layer (backend.db.connection).
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.connection import get_connection
from backend.tools.shopline_zendesk.db import binding_repo, store_repo

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ShoplineConfigValidation(BaseModel):
    shopline_domain: str
    shopline_access_token: str


class TenantConfigSetup(BaseModel):
    zendesk_subdomain: str
    shopline_domain: str
    shopline_access_token: str


# ---------------------------------------------------------------------------
# GET /config/{zendesk_subdomain}
# ---------------------------------------------------------------------------

@router.get("/config/{zendesk_subdomain}")
async def get_tenant_config(zendesk_subdomain: str):
    """Return Shopline credentials for a Zendesk subdomain.

    Queries shopline_zendesk.bindings JOIN stores.
    Returns 404 if no binding exists.
    """
    try:
        binding = binding_repo.get_binding_by_subdomain(zendesk_subdomain)
        if not binding:
            raise HTTPException(status_code=404, detail="Tenant not found")

        store = store_repo.get_store_by_id(binding["store_id"])
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")

        token_invalid = store.get("token_invalid", False)

        if not token_invalid and (not store.get("handle") or not store.get("access_token")):
            raise HTTPException(
                status_code=400,
                detail="Tenant Shopline configuration is incomplete",
            )

        return {
            "success": True,
            "data": {
                "shopline_domain": store["handle"],
                "shopline_access_token": store["access_token"],
                "handle": binding.get("handle", store["handle"]),
                "token_invalid": token_invalid,
                "zendesk_subdomain": zendesk_subdomain,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting tenant config for %s: %s", zendesk_subdomain, e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# POST /validate-shopline-config
# ---------------------------------------------------------------------------

@router.post("/validate-shopline-config")
async def validate_shopline_config(config: ShoplineConfigValidation):
    """Validate Shopline credentials by calling the Shopline API."""
    try:
        url = (
            f"https://{config.shopline_domain}.myshopline.com"
            f"/admin/openapi/v20250601/merchants/shop.json"
        )
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.shopline_access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                timeout=10.0,
            )

        if response.status_code == 200:
            return {"success": True, "data": {"valid": True, "message": "Shopline configuration is valid"}}

        logger.error("Shopline validation failed: %s - %s", response.status_code, response.text)
        return {"success": False, "error": f"Invalid configuration: {response.status_code}", "data": {"valid": False}}

    except httpx.TimeoutException:
        return {"success": False, "error": "Validation timeout - please check the domain", "data": {"valid": False}}
    except Exception as e:
        logger.error("Error validating Shopline config: %s", e)
        return {"success": False, "error": str(e), "data": {"valid": False}}


# ---------------------------------------------------------------------------
# POST /setup-config
# ---------------------------------------------------------------------------

@router.post("/setup-config")
async def setup_tenant_config(config: TenantConfigSetup):
    """Validate and save tenant configuration.

    1. Validate Shopline credentials.
    2. Upsert into shopline_zendesk.stores.
    3. Upsert into shopline_zendesk.bindings.
    """
    try:
        # Validate first
        url = (
            f"https://{config.shopline_domain}.myshopline.com"
            f"/admin/openapi/v20250601/merchants/shop.json"
        )
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.shopline_access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                timeout=10.0,
            )

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Invalid Shopline configuration: {response.status_code}",
                "data": {"valid": False},
            }

        # Upsert store
        store = store_repo.upsert_store(
            handle=config.shopline_domain,
            access_token=config.shopline_access_token,
            expires_at=datetime.utcnow(),  # manual setup — no real expiry
            scopes="read_customers,read_orders",
        )

        # Upsert binding
        from backend.tools.shopline_zendesk.services import api_key_service

        api_key = api_key_service.generate_api_key()
        binding_repo.upsert_binding(
            store_id=store["id"],
            zendesk_subdomain=config.zendesk_subdomain,
            api_key=api_key,
        )

        logger.info("Tenant config saved: %s → %s", config.zendesk_subdomain, config.shopline_domain)
        return {
            "success": True,
            "data": {
                "message": "Configuration saved successfully",
                "handle": config.shopline_domain,
            },
        }

    except httpx.TimeoutException:
        return {"success": False, "error": "Validation timeout - please check the domain"}
    except Exception as e:
        logger.error("Error setting up tenant config: %s", e)
        return {"success": False, "error": str(e)}
