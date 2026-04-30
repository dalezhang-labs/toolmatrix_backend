# Stripe Webhook Setup and Troubleshooting Guide

## Overview

This guide explains how to properly configure Stripe webhooks to sync subscription data between Stripe and the PostgreSQL database.

## Architecture

The webhook flow works as follows:

1. **Stripe** → sends webhook events to **Frontend webhook endpoint** (`/api/stripe/webhooks`)
2. **Frontend webhook** → processes and forwards to **Backend API** (`/api/stripe/subscriptions`, `/api/users/*`)
3. **Backend API** → stores data in **PostgreSQL database**

## Configuration Steps

### 1. Backend Configuration

Ensure these environment variables are set in your backend deployment:

```bash
# Required Stripe configuration
STRIPE_SECRET_KEY=sk_test_or_live_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_endpoint_secret

# Database configuration
DATABASE_URL=postgresql://user:password@host:port/database
```

### 2. Stripe Dashboard Setup

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Set endpoint URL to: `https://your-frontend-domain.vercel.app/api/stripe/webhooks`
4. Select these events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated` 
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click **"Add endpoint"**
6. Copy the **Signing secret** (starts with `whsec_`)
7. Set `STRIPE_WEBHOOK_SECRET` environment variable to this value

### 3. Frontend Configuration

Set these environment variables in your frontend (Vercel) deployment:

```bash
# Stripe configuration
STRIPE_SECRET_KEY=sk_test_or_live_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_endpoint_secret

# Backend API URL
NEXT_PUBLIC_BACKEND_URL=https://your-backend-domain.onrender.com
```

## Database Tables

The following tables are used to store subscription data:

### site_users
- Main user table for website users
- Links users by email to Stripe customers

### user_stripe_subscriptions  
- Stores subscription details from Stripe
- Links to `site_users` table via `user_id`
- Tracks subscription status, amounts, periods

### webhook_events
- Logs all webhook events for debugging
- Prevents duplicate processing
- Tracks processing status

### payment_history
- Records payment transactions
- Links invoices to subscriptions and users

## Webhook Endpoints

### Frontend Webhook Endpoint

**URL:** `/api/stripe/webhooks`
**Method:** POST
**Purpose:** Receives Stripe webhooks, validates signatures, processes events

**Supported Events:**
- `customer.subscription.created` → Creates new subscription record
- `customer.subscription.updated` → Updates existing subscription  
- `customer.subscription.deleted` → Marks subscription as canceled
- `invoice.payment_succeeded` → Records successful payment
- `invoice.payment_failed` → Records failed payment

### Backend API Endpoints

**User Management:**
- `GET /api/users/email/{email}` → Find user by email
- `POST /api/users/register` → Create new user
- `PUT /api/users/{user_id}` → Update user info

**Subscription Management:**
- `POST /api/users/{user_id}/subscriptions` → Create subscription
- `PUT /api/users/{user_id}/subscriptions/{stripe_subscription_id}` → Update subscription
- `GET /api/users/{user_id}/subscriptions` → Get user subscriptions

**Webhook Event Logging:**
- `POST /api/stripe/webhooks/events` → Record webhook event
- `POST /api/stripe/webhooks` → Alternative backend webhook endpoint

## Testing Webhooks

### 1. Using Stripe CLI

```bash
# Install Stripe CLI
curl -s https://packages.stripe.com/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.com/stripe-cli-deb/ stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list
sudo apt update
sudo apt install stripe

# Login to Stripe
stripe login

# Forward webhooks to local development
stripe listen --forward-to localhost:3000/api/stripe/webhooks

# Trigger test events
stripe trigger customer.subscription.created
stripe trigger customer.subscription.updated  
stripe trigger invoice.payment_succeeded
```

### 2. Manual Testing

1. Create a test subscription in Stripe Dashboard
2. Update the subscription (change plan, cancel, etc.)
3. Check your webhook endpoint logs
4. Verify data appears in database

## Troubleshooting

### Common Issues

#### 1. Webhook Signature Verification Failed

**Symptoms:**
- HTTP 400 responses from webhook endpoint
- "Webhook signature verification failed" errors

**Solutions:**
- Verify `STRIPE_WEBHOOK_SECRET` matches Stripe Dashboard
- Ensure webhook secret is from the correct endpoint
- Check that raw request body is being used for verification

#### 2. User Not Found

**Symptoms:**
- Webhook processes but subscription not created
- "User not found for email" errors

**Solutions:**
- Ensure user exists in `site_users` table before subscription creation
- Check that Stripe customer email matches user email exactly
- Create user first via registration or admin panel

#### 3. Subscription Not Updating

**Symptoms:**
- Subscription created but never updates
- Old subscription data in database

**Solutions:**
- Verify `customer.subscription.updated` event is enabled in Stripe
- Check webhook logs for update events
- Ensure update endpoint is working: `PUT /api/users/{user_id}/subscriptions/{stripe_subscription_id}`

#### 4. Database Connection Errors

**Symptoms:**
- HTTP 500 errors from backend
- Database connection timeout errors

**Solutions:**
- Verify `DATABASE_URL` is correctly configured
- Check database server status and connectivity
- Ensure database tables exist (run migrations)

#### 5. CORS Errors

**Symptoms:**
- Requests blocked by browser
- "Access-Control-Allow-Origin" errors

**Solutions:**
- Backend CORS is configured to allow all origins (`*`)
- Verify frontend is making requests to correct backend URL
- Check `NEXT_PUBLIC_BACKEND_URL` environment variable

### Debugging Steps

1. **Check webhook endpoint logs** in Vercel/deployment platform
2. **Verify webhook events** are being sent from Stripe Dashboard
3. **Test backend API endpoints** directly with curl/Postman
4. **Check database tables** for expected data
5. **Review Stripe Dashboard** webhook delivery logs

### Logging and Monitoring

The webhook system includes comprehensive logging:

- ✅ Successful operations
- ⚠️ Warnings (non-critical issues)  
- ❌ Errors (failures that need attention)
- 🔄 Processing status
- 🔍 Data lookups
- 📝 Database operations

Monitor these logs to identify and resolve issues quickly.

## Production Checklist

- [ ] Stripe webhook endpoint configured with production URL
- [ ] `STRIPE_WEBHOOK_SECRET` set to production value
- [ ] `STRIPE_SECRET_KEY` set to live key (not test key)
- [ ] Database connection working and tables exist
- [ ] Backend deployed and accessible
- [ ] Frontend deployed with correct `NEXT_PUBLIC_BACKEND_URL`
- [ ] Test webhook events working end-to-end
- [ ] Monitoring and alerting set up for webhook failures

## Support

For additional help:

1. Check Stripe Dashboard webhook logs
2. Review application logs in deployment platform
3. Test individual API endpoints
4. Verify database table contents
5. Contact development team with specific error messages and steps to reproduce