-- Migration: Unify ZAF + Shopline Frontend onto shopline_zendesk schema.
--
-- Previously the ZAF app used public.tenants (via SQLAlchemy) while the
-- Shopline Frontend used shopline_zendesk.stores + bindings (via psycopg2).
-- This migration:
--   1. Drops the UNIQUE constraint on bindings.store_id (one store can
--      bind to multiple Zendesk subdomains).
--   2. Migrates data from public.tenants into shopline_zendesk.stores
--      and shopline_zendesk.bindings.
--
-- Idempotent: safe to run multiple times.

-- Step 1: Enforce one-store-per-binding (store_id UNIQUE),
-- allow one-subdomain-to-many-stores (zendesk_subdomain non-unique).
DROP INDEX IF EXISTS shopline_zendesk.bindings_store_id_idx;
CREATE UNIQUE INDEX IF NOT EXISTS bindings_store_id_idx
  ON shopline_zendesk.bindings(store_id);

ALTER TABLE shopline_zendesk.bindings
  DROP CONSTRAINT IF EXISTS bindings_zendesk_subdomain_key;

CREATE INDEX IF NOT EXISTS bindings_zendesk_subdomain_idx
  ON shopline_zendesk.bindings(zendesk_subdomain);

-- Step 2: Migrate stores (deduplicate by shopline_domain)
INSERT INTO shopline_zendesk.stores (handle, access_token, expires_at, scopes)
SELECT DISTINCT ON (t.shopline_domain)
       t.shopline_domain,
       t.shopline_access_token,
       NOW() + INTERVAL '30 days',
       'read_customers,read_orders'
FROM public.tenants t
WHERE t.shopline_domain IS NOT NULL
  AND t.shopline_access_token IS NOT NULL
ORDER BY t.shopline_domain, t.created_at ASC
ON CONFLICT (handle) DO NOTHING;

-- Step 3: Migrate bindings
INSERT INTO shopline_zendesk.bindings (store_id, zendesk_subdomain, api_key)
SELECT s.id, t.zendesk_subdomain, t.shopline_domain
FROM public.tenants t
JOIN shopline_zendesk.stores s ON s.handle = t.shopline_domain
WHERE t.shopline_domain IS NOT NULL
  AND t.shopline_access_token IS NOT NULL
ON CONFLICT (zendesk_subdomain) DO NOTHING;
