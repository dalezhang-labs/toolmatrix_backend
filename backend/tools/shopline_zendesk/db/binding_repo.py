"""CRUD operations for shopline_zendesk.bindings table."""

from __future__ import annotations

import logging

from backend.db.connection import get_connection

logger = logging.getLogger(__name__)


def upsert_binding(
    store_id: str,
    zendesk_subdomain: str,
    api_key: str,
    zendesk_admin_email: str | None = None,
    zendesk_api_token: str | None = None,
) -> dict:
    """Insert a new binding or update on store_id conflict (one-to-one).

    Returns the upserted row as a dict (includes computed
    ``has_zendesk_credentials`` key).
    """
    sql = """
        INSERT INTO shopline_zendesk.bindings
            (store_id, zendesk_subdomain, api_key,
             zendesk_admin_email, zendesk_api_token)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (store_id) DO UPDATE
          SET zendesk_subdomain   = EXCLUDED.zendesk_subdomain,
              api_key             = EXCLUDED.api_key,
              zendesk_admin_email = EXCLUDED.zendesk_admin_email,
              zendesk_api_token   = EXCLUDED.zendesk_api_token,
              updated_at          = NOW()
        RETURNING id, store_id, zendesk_subdomain, api_key,
                  zendesk_admin_email, zendesk_api_token,
                  created_at, updated_at
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (store_id, zendesk_subdomain, api_key,
                 zendesk_admin_email, zendesk_api_token),
            )
            row = cur.fetchone()
    return _row_to_dict(row)


def get_binding_by_handle(handle: str) -> dict | None:
    """Look up a binding by Shopline store handle.

    JOINs with shopline_zendesk.stores to resolve handle -> store_id -> binding.
    Returns None if no binding exists for the handle.
    """
    sql = """
        SELECT b.id, b.store_id, b.zendesk_subdomain, b.api_key,
               b.zendesk_admin_email, b.zendesk_api_token,
               b.created_at, b.updated_at, s.handle
        FROM shopline_zendesk.bindings b
        JOIN shopline_zendesk.stores s ON s.id = b.store_id
        WHERE s.handle = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (handle,))
            row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict_with_handle(row)


def get_binding_by_subdomain(zendesk_subdomain: str) -> dict | None:
    """Look up a binding by Zendesk subdomain.

    JOINs with shopline_zendesk.stores to include the store handle.
    Returns None if no binding exists for the subdomain.
    """
    sql = """
        SELECT b.id, b.store_id, b.zendesk_subdomain, b.api_key,
               b.zendesk_admin_email, b.zendesk_api_token,
               b.created_at, b.updated_at, s.handle
        FROM shopline_zendesk.bindings b
        JOIN shopline_zendesk.stores s ON s.id = b.store_id
        WHERE b.zendesk_subdomain = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (zendesk_subdomain,))
            row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict_with_handle(row)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COLUMNS = (
    "id",
    "store_id",
    "zendesk_subdomain",
    "api_key",
    "zendesk_admin_email",
    "zendesk_api_token",
    "created_at",
    "updated_at",
)

_COLUMNS_WITH_HANDLE = _COLUMNS + ("handle",)


def _has_zendesk_credentials(email: str | None, token: str | None) -> bool:
    """Return True if both zendesk_admin_email and zendesk_api_token are set."""
    return bool(email) and bool(token)


def _row_to_dict(row: tuple) -> dict:
    """Convert a bindings row tuple to a dict keyed by column name."""
    d = dict(zip(_COLUMNS, row))
    d["has_zendesk_credentials"] = _has_zendesk_credentials(
        d.get("zendesk_admin_email"), d.get("zendesk_api_token"),
    )
    return d


def _row_to_dict_with_handle(row: tuple) -> dict:
    """Convert a bindings+handle row tuple to a dict keyed by column name."""
    d = dict(zip(_COLUMNS_WITH_HANDLE, row))
    d["has_zendesk_credentials"] = _has_zendesk_credentials(
        d.get("zendesk_admin_email"), d.get("zendesk_api_token"),
    )
    return d
