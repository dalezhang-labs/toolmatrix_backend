-- Phase 2 migration: Add Zendesk API credentials to bindings table.
-- These columns store the admin email and API token needed for
-- server-to-server Zendesk REST API authentication (HTTP Basic Auth).
-- Columns are nullable to support existing bindings that don't have
-- credentials yet; the frontend will prompt merchants to update.
--
-- Idempotent: safe to run multiple times via ADD COLUMN IF NOT EXISTS.

ALTER TABLE shopline_zendesk.bindings
  ADD COLUMN IF NOT EXISTS zendesk_admin_email TEXT;

ALTER TABLE shopline_zendesk.bindings
  ADD COLUMN IF NOT EXISTS zendesk_api_token TEXT;
