# Shopline-Zendesk Route Ownership

This backend serves **two frontend applications**:

1. Shopline App frontend (`toolmatrix/shopline-zendesk-frontend`)
2. Zendesk ZAF frontend (`toolmatrix/zendesk-zaf-app-for-shopline`)

Route mounting is centralized in `mounts.py`:

- `include_shopline_frontend_routes(app)`
  - Prefix: `/api/shopline-zendesk/shopline`
  - Source modules: `routes/shopline/*`
- `include_zaf_frontend_routes(app)`
  - Legacy prefix: `/api/shopline-zendesk/zendesk`
  - V2 prefixes: `/api/customers`, `/api/orders`, `/api/logistics`, `/api/subscriptions`, `/api/tenants`, `/api/users`, `/api/stripe`
  - Source modules: `routes/zendesk/*` + `routes/zendesk/app/routers/*`

This split keeps route responsibility aligned with frontend ownership and
makes Railway deployment troubleshooting easier.
