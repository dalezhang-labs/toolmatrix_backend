from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
from ..models.base import ApiResponse
from ..database import get_db
import logging
from datetime import datetime
from pydantic import BaseModel
import uuid
import json

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response Models
class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None
    google_id: Optional[str] = None
    image_url: Optional[str] = None
    stripe_customer_id: Optional[str] = None

class UserUpdate(BaseModel):
    stripe_customer_id: Optional[str] = None
    name: Optional[str] = None
    image_url: Optional[str] = None

class SubscriptionCreate(BaseModel):
    user_id: str
    stripe_subscription_id: str
    stripe_customer_id: str
    plan_id: Optional[str] = None
    status: str
    current_period_start: datetime
    current_period_end: datetime
    amount: int
    currency: str = "usd"
    interval_type: str = "month"

class SubscriptionUpdate(BaseModel):
    status: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None

class PaymentRecord(BaseModel):
    user_id: str
    subscription_id: Optional[str] = None
    stripe_invoice_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    amount: int
    currency: str = "usd"
    status: str
    payment_method_type: Optional[str] = None

class WebhookEvent(BaseModel):
    stripe_event_id: str
    event_type: str
    event_data: Dict[str, Any]

@router.get("/users/email/{email}", response_model=ApiResponse)
async def get_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    """Get user by email address"""
    try:
        query = text("SELECT * FROM omnigatech.site_users WHERE email = :email AND is_active = true")
        result = await db.execute(query, {"email": email})
        user = result.first()
        
        if user:
            return ApiResponse(
                success=True,
                data={
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "google_id": user.google_id,
                    "image_url": user.image_url,
                    "stripe_customer_id": user.stripe_customer_id,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
            )
        else:
            return ApiResponse(
                success=True,
                data=None,
                message="User not found"
            )
    except Exception as e:
        logger.error(f"Error fetching user by email: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/users", response_model=ApiResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user"""
    try:
        user_id = str(uuid.uuid4())
        query = text("""
            INSERT INTO omnigatech.site_users (id, email, name, google_id, image_url, stripe_customer_id, created_at, updated_at, is_active)
            VALUES (:id, :email, :name, :google_id, :image_url, :stripe_customer_id, NOW(), NOW(), true)
            RETURNING *
        """)
        
        result = await db.execute(query, {
            "id": user_id,
            "email": user_data.email,
            "name": user_data.name,
            "google_id": user_data.google_id,
            "image_url": user_data.image_url,
            "stripe_customer_id": user_data.stripe_customer_id
        })
        
        await db.commit()
        user = result.first()
        
        return ApiResponse(
            success=True,
            data={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "stripe_customer_id": user.stripe_customer_id
            }
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating user: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.put("/users/{user_id}", response_model=ApiResponse)
async def update_user(user_id: str, user_data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """Update user information"""
    try:
        updates = []
        params = {"user_id": user_id}
        
        if user_data.stripe_customer_id is not None:
            updates.append("stripe_customer_id = :stripe_customer_id")
            params["stripe_customer_id"] = user_data.stripe_customer_id
            
        if user_data.name is not None:
            updates.append("name = :name")
            params["name"] = user_data.name
            
        if user_data.image_url is not None:
            updates.append("image_url = :image_url")
            params["image_url"] = user_data.image_url
        
        if updates:
            updates.append("updated_at = NOW()")
            query = text(f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id")
            await db.execute(query, params)
            await db.commit()
        
        return ApiResponse(
            success=True,
            message="User updated successfully"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/plans", response_model=ApiResponse)
async def get_subscription_plans(db: AsyncSession = Depends(get_db)):
    """Get all active subscription plans"""
    try:
        from sqlalchemy import text
        query = text("""
            SELECT id, stripe_price_id, stripe_product_id, name, description, 
                   amount, currency, interval, interval_count, trial_period_days
            FROM omnigatech.subscription_plans 
            WHERE is_active = true 
            ORDER BY amount ASC
        """)
        result = await db.execute(query)
        plans = []
        
        for row in result:
            plans.append({
                "id": row.id,
                "stripe_price_id": row.stripe_price_id,
                "stripe_product_id": row.stripe_product_id,
                "name": row.name,
                "description": row.description,
                "amount": row.amount,
                "currency": row.currency,
                "interval": row.interval,
                "interval_count": row.interval_count,
                "trial_period_days": row.trial_period_days
            })
        
        return ApiResponse(
            success=True,
            data=plans
        )
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/subscriptions/user/{user_id}", response_model=ApiResponse)
async def get_user_subscriptions(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get all subscriptions for a user"""
    try:
        query = text("""
            SELECT s.*, p.name as plan_name, p.description as plan_description
            FROM omnigatech.user_subscriptions s
            LEFT JOIN subscription_plans p ON s.plan_id = p.id
            WHERE s.user_id = :user_id
            ORDER BY s.created_at DESC
        """)
        result = await db.execute(query, {"user_id": user_id})
        subscriptions = []
        
        for row in result:
            subscriptions.append({
                "id": row.id,
                "stripe_subscription_id": row.stripe_subscription_id,
                "status": row.status,
                "plan_name": row.plan_name,
                "plan_description": row.plan_description,
                "amount": row.amount,
                "currency": row.currency,
                "interval_type": row.interval_type,
                "current_period_start": row.current_period_start,
                "current_period_end": row.current_period_end,
                "cancel_at_period_end": row.cancel_at_period_end
            })
        
        return ApiResponse(
            success=True,
            data=subscriptions
        )
    except Exception as e:
        logger.error(f"Error fetching user subscriptions: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/subscriptions", response_model=ApiResponse)
async def create_subscription(sub_data: SubscriptionCreate, db: AsyncSession = Depends(get_db)):
    """Create a new subscription record"""
    try:
        sub_id = str(uuid.uuid4())
        query = text("""
            INSERT INTO omnigatech.user_subscriptions (
                id, user_id, stripe_subscription_id, stripe_customer_id, plan_id,
                status, current_period_start, current_period_end, amount, currency,
                interval_type, created_at, updated_at
            ) VALUES (
                :id, :user_id, :stripe_subscription_id, :stripe_customer_id, :plan_id,
                :status, :current_period_start, :current_period_end, :amount, :currency,
                :interval_type, NOW(), NOW()
            )
        """)
        
        await db.execute(query, {
            "id": sub_id,
            "user_id": sub_data.user_id,
            "stripe_subscription_id": sub_data.stripe_subscription_id,
            "stripe_customer_id": sub_data.stripe_customer_id,
            "plan_id": sub_data.plan_id,
            "status": sub_data.status,
            "current_period_start": sub_data.current_period_start,
            "current_period_end": sub_data.current_period_end,
            "amount": sub_data.amount,
            "currency": sub_data.currency,
            "interval_type": sub_data.interval_type
        })
        
        await db.commit()
        
        return ApiResponse(
            success=True,
            data={"id": sub_id},
            message="Subscription created successfully"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating subscription: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.put("/subscriptions/{stripe_subscription_id}", response_model=ApiResponse)
async def update_subscription(
    stripe_subscription_id: str, 
    sub_data: SubscriptionUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update subscription by Stripe subscription ID"""
    try:
        updates = []
        params = {"stripe_subscription_id": stripe_subscription_id}
        
        if sub_data.status is not None:
            updates.append("status = :status")
            params["status"] = sub_data.status
            
        if sub_data.current_period_end is not None:
            updates.append("current_period_end = :current_period_end")
            params["current_period_end"] = sub_data.current_period_end
            
        if sub_data.cancel_at_period_end is not None:
            updates.append("cancel_at_period_end = :cancel_at_period_end")
            params["cancel_at_period_end"] = sub_data.cancel_at_period_end
        
        if updates:
            updates.append("updated_at = NOW()")
            query = text(f"""
                UPDATE omnigatech.user_subscriptions 
                SET {', '.join(updates)} 
                WHERE stripe_subscription_id = :stripe_subscription_id
            """)
            await db.execute(query, params)
            await db.commit()
        
        return ApiResponse(
            success=True,
            message="Subscription updated successfully"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating subscription: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/payments", response_model=ApiResponse)
async def record_payment(payment_data: PaymentRecord, db: AsyncSession = Depends(get_db)):
    """Record a payment transaction"""
    try:
        payment_id = str(uuid.uuid4())
        query = text("""
            INSERT INTO omnigatech.payment_history (
                id, user_id, subscription_id, stripe_invoice_id, stripe_payment_intent_id,
                amount, currency, status, payment_method_type, created_at
            ) VALUES (
                :id, :user_id, :subscription_id, :stripe_invoice_id, :stripe_payment_intent_id,
                :amount, :currency, :status, :payment_method_type, NOW()
            )
        """)
        
        await db.execute(query, {
            "id": payment_id,
            "user_id": payment_data.user_id,
            "subscription_id": payment_data.subscription_id,
            "stripe_invoice_id": payment_data.stripe_invoice_id,
            "stripe_payment_intent_id": payment_data.stripe_payment_intent_id,
            "amount": payment_data.amount,
            "currency": payment_data.currency,
            "status": payment_data.status,
            "payment_method_type": payment_data.payment_method_type
        })
        
        await db.commit()
        
        return ApiResponse(
            success=True,
            data={"id": payment_id},
            message="Payment recorded successfully"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error recording payment: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/webhooks/events", response_model=ApiResponse)
async def record_webhook_event(event_data: WebhookEvent, db: AsyncSession = Depends(get_db)):
    """Record a Stripe webhook event"""
    try:
        event_id = str(uuid.uuid4())
        
        # Check if event already exists
        check_query = text("SELECT id FROM omnigatech.webhook_events WHERE stripe_event_id = :stripe_event_id")
        existing = await db.execute(check_query, {"stripe_event_id": event_data.stripe_event_id})
        
        if existing.first():
            return ApiResponse(
                success=True,
                message="Event already processed"
            )
        
        # Insert new event
        query = text("""
            INSERT INTO omnigatech.webhook_events (
                id, stripe_event_id, event_type, event_data, created_at, processed
            ) VALUES (
                :id, :stripe_event_id, :event_type, CAST(:event_data AS jsonb), NOW(), false
            )
        """)
        
        await db.execute(query, {
            "id": event_id,
            "stripe_event_id": event_data.stripe_event_id,
            "event_type": event_data.event_type,
            "event_data": json.dumps(event_data.event_data) if isinstance(event_data.event_data, dict) else str(event_data.event_data)
        })
        
        await db.commit()
        
        return ApiResponse(
            success=True,
            data={"id": event_id},
            message="Webhook event recorded"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error recording webhook event: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

class CheckoutSessionCreate(BaseModel):
    user_id: str
    email: str
    price_id: Optional[str] = None
    plan_name: Optional[str] = None
    amount: Optional[int] = None
    interval: Optional[str] = None
    success_url: str
    cancel_url: str

@router.post("/create-checkout-session", response_model=ApiResponse)
async def create_checkout_session(
    session_data: CheckoutSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe checkout session"""
    try:
        import stripe
        import os
        import json
        from pathlib import Path
        
        # Initialize Stripe with the secret key from config
        from ...config import settings
        stripe_key = settings.stripe_secret_key
        if not stripe_key:
            logger.error('STRIPE_SECRET_KEY not configured in backend')
            return ApiResponse(
                success=False,
                error="Payment system not configured on server"
            )
        
        stripe.api_key = stripe_key
        
        # Load standard plan IDs if available
        stripe_ids_path = Path(__file__).parent.parent / "config" / "stripe_ids.json"
        standard_plans = {}
        if stripe_ids_path.exists():
            with open(stripe_ids_path, 'r') as f:
                standard_plans = json.load(f)
        
        # Find or create Stripe customer
        customers = stripe.Customer.list(email=session_data.email, limit=1)
        if customers and len(customers.data) > 0:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=session_data.email,
                metadata={"user_id": session_data.user_id}
            )
        
        # Update user with Stripe customer ID if needed
        from ..models.user import SiteUserModel
        user_result = await db.execute(
            select(SiteUserModel).where(SiteUserModel.id == session_data.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user and not user.stripe_customer_id:
            user.stripe_customer_id = customer.id
            await db.commit()
        
        # Create checkout session parameters
        checkout_params = {
            'mode': 'subscription',
            'customer': customer.id,
            'success_url': session_data.success_url,
            'cancel_url': session_data.cancel_url,
            'payment_method_types': ['card'],
            'allow_promotion_codes': True,
        }
        
        # Add line items based on price_id or dynamic pricing
        if session_data.price_id:
            checkout_params['line_items'] = [{
                'price': session_data.price_id,
                'quantity': 1
            }]
        elif session_data.plan_name and session_data.amount and session_data.interval:
            # Check if this is a standard plan
            if session_data.plan_name in standard_plans:
                plan_config = standard_plans[session_data.plan_name]
                
                # Determine which price to use based on interval
                if session_data.interval == 'month' and plan_config['monthly_amount'] == session_data.amount:
                    # Use pre-configured monthly price ID
                    logger.info(f"Using standard monthly plan: {session_data.plan_name} - {plan_config['monthly_price_id']}")
                    checkout_params['line_items'] = [{
                        'price': plan_config['monthly_price_id'],
                        'quantity': 1
                    }]
                elif session_data.interval == 'year' and plan_config['yearly_amount'] == session_data.amount:
                    # Use pre-configured yearly price ID
                    logger.info(f"Using standard yearly plan: {session_data.plan_name} - {plan_config['yearly_price_id']}")
                    checkout_params['line_items'] = [{
                        'price': plan_config['yearly_price_id'],
                        'quantity': 1
                    }]
                else:
                    # Amount doesn't match standard plan, treat as custom
                    expected = plan_config['monthly_amount'] if session_data.interval == 'month' else plan_config['yearly_amount']
                    logger.warning(f"Plan {session_data.plan_name} amount {session_data.amount} doesn't match standard {expected}")
                    # Create custom product/price
                    product_name = f"{session_data.plan_name} Plan (Custom)"
                    product = stripe.Product.create(
                        name=product_name,
                        description=f"Custom {session_data.plan_name} subscription"
                    )
                    matching_price = stripe.Price.create(
                        product=product.id,
                        unit_amount=session_data.amount,
                        currency='usd',
                        recurring={'interval': session_data.interval}
                    )
                    checkout_params['line_items'] = [{
                        'price': matching_price.id,
                        'quantity': 1
                    }]
            else:
                # Not a standard plan, search for existing or create new
                product_name = f"{session_data.plan_name} Plan"
                existing_products = stripe.Product.search(
                    query=f"name:'{product_name}' AND active:'true'",
                    limit=1
                )
                
                if existing_products and len(existing_products.data) > 0:
                    product = existing_products.data[0]
                    logger.info(f"Reusing existing product: {product.id} - {product.name}")
                    
                    # Search for existing price
                    existing_prices = stripe.Price.list(
                        product=product.id,
                        active=True,
                        type='recurring',
                        limit=100
                    )
                    
                    # Find matching price
                    matching_price = None
                    for price in existing_prices.data:
                        if (price.unit_amount == session_data.amount and 
                            price.currency == 'usd' and
                            price.recurring and 
                            price.recurring.interval == session_data.interval):
                            matching_price = price
                            logger.info(f"Reusing existing price: {price.id}")
                            break
                    
                    if not matching_price:
                        # Create new price for existing product
                        matching_price = stripe.Price.create(
                            product=product.id,
                            unit_amount=session_data.amount,
                            currency='usd',
                            recurring={'interval': session_data.interval}
                        )
                        logger.info(f"Created new price for existing product: {matching_price.id}")
                else:
                    # Create new product only if it doesn't exist
                    product = stripe.Product.create(
                        name=product_name,
                        description=f"{session_data.plan_name} subscription plan"
                    )
                    logger.info(f"Created new product: {product.id} - {product.name}")
                    
                    matching_price = stripe.Price.create(
                        product=product.id,
                        unit_amount=session_data.amount,
                        currency='usd',
                        recurring={'interval': session_data.interval}
                    )
                    logger.info(f"Created new price: {matching_price.id}")
                
                checkout_params['line_items'] = [{
                    'price': matching_price.id,
                    'quantity': 1
                }]
        else:
            return ApiResponse(
                success=False,
                error="Either price_id or plan details (name, amount, interval) required"
            )
        
        # Add subscription metadata
        checkout_params['subscription_data'] = {
            'metadata': {
                'user_id': session_data.user_id,
                'plan': session_data.plan_name or 'subscription'
            }
        }
        
        # Create the checkout session
        checkout = stripe.checkout.Session.create(**checkout_params)
        
        return ApiResponse(
            success=True,
            data={
                "session_id": checkout.id,
                "url": checkout.url
            }
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

class PortalSessionCreate(BaseModel):
    user_id: str
    email: str
    return_url: str

@router.post("/create-portal-session", response_model=ApiResponse)
async def create_portal_session(
    portal_data: PortalSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe billing portal session for managing subscriptions"""
    try:
        import stripe
        from ...config import settings
        
        stripe_key = settings.stripe_secret_key
        if not stripe_key:
            logger.error('STRIPE_SECRET_KEY not configured in backend')
            return ApiResponse(
                success=False,
                error="Payment system not configured on server"
            )
        
        stripe.api_key = stripe_key
        
        # Find the user's Stripe customer ID
        from ..models.user import SiteUserModel
        user_result = await db.execute(
            select(SiteUserModel).where(SiteUserModel.id == portal_data.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return ApiResponse(
                success=False,
                error="User not found"
            )
        
        # Get or create Stripe customer
        customer_id = user.stripe_customer_id
        
        if not customer_id:
            # Find existing customer by email
            customers = stripe.Customer.list(email=portal_data.email, limit=1)
            if customers and len(customers.data) > 0:
                customer = customers.data[0]
                customer_id = customer.id
                
                # Update user with the customer ID
                user.stripe_customer_id = customer_id
                await db.commit()
            else:
                # Create new customer
                customer = stripe.Customer.create(
                    email=portal_data.email,
                    metadata={"user_id": portal_data.user_id}
                )
                customer_id = customer.id
                
                # Update user with the customer ID
                user.stripe_customer_id = customer_id
                await db.commit()
        
        # Create the billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=portal_data.return_url,
        )
        
        return ApiResponse(
            success=True,
            data={
                "url": portal_session.url
            }
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/webhooks", response_model=ApiResponse)
async def handle_stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events with proper signature verification"""
    try:
        import stripe
        from ...config import settings
        
        # Initialize Stripe
        stripe_key = settings.stripe_secret_key
        webhook_secret = settings.stripe_webhook_secret
        
        if not stripe_key or not webhook_secret:
            logger.error('Stripe keys not configured properly')
            return ApiResponse(
                success=False,
                error="Stripe configuration missing"
            )
        
        stripe.api_key = stripe_key
        
        # Get raw body and signature
        body = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not sig_header:
            logger.error('Missing Stripe signature header')
            return ApiResponse(
                success=False,
                error="Missing Stripe signature"
            )
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                body, sig_header, webhook_secret
            )
        except ValueError as e:
            logger.error(f'Invalid payload: {e}')
            return ApiResponse(
                success=False,
                error="Invalid payload"
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error(f'Invalid signature: {e}')
            return ApiResponse(
                success=False,
                error="Invalid signature"
            )
        
        # Record webhook event (check for duplicates)
        event_id = str(uuid.uuid4())
        check_query = text("SELECT id FROM omnigatech.webhook_events WHERE stripe_event_id = :stripe_event_id")
        existing = await db.execute(check_query, {"stripe_event_id": event['id']})
        
        if existing.first():
            logger.info(f"Webhook event {event['id']} already processed")
            return ApiResponse(
                success=True,
                message="Event already processed"
            )
        
        # Insert new event
        insert_query = text("""
            INSERT INTO omnigatech.webhook_events (
                id, stripe_event_id, event_type, event_data, created_at, processed
            ) VALUES (
                :id, :stripe_event_id, :event_type, CAST(:event_data AS jsonb), NOW(), false
            )
        """)
        
        await db.execute(insert_query, {
            "id": event_id,
            "stripe_event_id": event['id'],
            "event_type": event['type'],
            "event_data": json.dumps(event)
        })
        
        # Process the webhook event
        success = await process_webhook_event(event, db)
        
        # Mark event as processed if successful
        if success:
            await db.execute(
                text("UPDATE webhook_events SET processed = true WHERE stripe_event_id = :stripe_event_id"),
                {"stripe_event_id": event['id']}
            )
        
        await db.commit()
        
        return ApiResponse(
            success=success,
            message="Webhook processed successfully" if success else "Webhook processing failed"
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        await db.rollback()
        return ApiResponse(
            success=False,
            error=str(e)
        )

async def process_webhook_event(event: dict, db: AsyncSession) -> bool:
    """Process individual webhook events"""
    try:
        import stripe
        from ...config import settings
        stripe.api_key = settings.stripe_secret_key
        
        event_type = event['type']
        logger.info(f"Processing webhook event: {event_type}")
        
        if event_type in [
            'customer.subscription.created', 
            'customer.subscription.updated',
            'customer.subscription.deleted'
        ]:
            return await handle_subscription_webhook(event, db)
        elif event_type in [
            'invoice.payment_succeeded',
            'invoice.payment_failed'
        ]:
            return await handle_invoice_webhook(event, db)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return True  # Return true for unhandled events
            
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        return False

async def handle_subscription_webhook(event: dict, db: AsyncSession) -> bool:
    """Handle subscription-related webhook events"""
    try:
        import stripe
        from ...config import settings
        stripe.api_key = settings.stripe_secret_key
        
        subscription = event['data']['object']
        event_type = event['type']
        
        logger.info(f"Processing subscription {event_type}: {subscription['id']}")
        
        # Get customer email from Stripe
        customer = stripe.Customer.retrieve(subscription['customer'])
        if not customer.email:
            logger.error(f"Customer email not found for subscription: {subscription['id']}")
            return False
        
        # Find user in database
        user_query = text("SELECT * FROM omnigatech.site_users WHERE email = :email AND is_active = true")
        user_result = await db.execute(user_query, {"email": customer.email})
        user = user_result.first()
        
        if not user:
            logger.error(f"User not found for email: {customer.email}")
            return False
        
        # Get product name for plan
        plan_name = 'Subscription'
        if subscription['items']['data']:
            price_id = subscription['items']['data'][0]['price']['id']
            product_id = subscription['items']['data'][0]['price']['product']
            
            try:
                product = stripe.Product.retrieve(product_id)
                plan_name = product.name
            except Exception as e:
                logger.warning(f"Could not fetch product name: {e}")
        
        if event_type == 'customer.subscription.created':
            # Create new subscription record
            subscription_id = str(uuid.uuid4())
            
            # Handle incomplete subscriptions which may not have period dates
            current_period_start = None
            current_period_end = None
            
            if subscription.get('current_period_start'):
                current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
            elif subscription.get('created'):
                # Use created date as fallback
                current_period_start = datetime.fromtimestamp(subscription['created'])
            
            if subscription.get('current_period_end'):
                current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
            
            insert_query = text("""
                INSERT INTO omnigatech.user_stripe_subscriptions (
                    id, user_id, stripe_subscription_id, stripe_customer_id, plan_name,
                    status, current_period_start, current_period_end, amount, currency,
                    interval, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :stripe_subscription_id, :stripe_customer_id, :plan_name,
                    :status, :current_period_start, :current_period_end, :amount, :currency,
                    :interval, NOW(), NOW()
                )
            """)
            
            await db.execute(insert_query, {
                "id": subscription_id,
                "user_id": user.id,
                "stripe_subscription_id": subscription['id'],
                "stripe_customer_id": subscription['customer'],
                "plan_name": plan_name,
                "status": subscription['status'],
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "amount": subscription['items']['data'][0]['price']['unit_amount'] if subscription['items']['data'] else 0,
                "currency": subscription['items']['data'][0]['price']['currency'] if subscription['items']['data'] else 'usd',
                "interval": subscription['items']['data'][0]['price']['recurring']['interval'] if subscription['items']['data'] else 'month'
            })
            
            logger.info(f"Created subscription record for user {user.id}")
            
        elif event_type in ['customer.subscription.updated', 'customer.subscription.deleted']:
            # Update existing subscription record
            update_fields = ["status = :status", "updated_at = NOW()"]
            params = {
                "stripe_subscription_id": subscription['id'],
                "status": subscription['status']
            }
            
            if event_type == 'customer.subscription.updated':
                # Only update period end if it exists
                if subscription.get('current_period_end'):
                    update_fields.append("current_period_end = :current_period_end")
                    params["current_period_end"] = datetime.fromtimestamp(subscription['current_period_end'])
                
                update_fields.append("cancel_at_period_end = :cancel_at_period_end")
                params["cancel_at_period_end"] = subscription.get('cancel_at_period_end', False)
            elif event_type == 'customer.subscription.deleted':
                update_fields.append("canceled_at = NOW()")
            
            update_query = text(f"""
                UPDATE omnigatech.user_stripe_subscriptions 
                SET {', '.join(update_fields)}
                WHERE stripe_subscription_id = :stripe_subscription_id
            """)
            
            result = await db.execute(update_query, params)
            if result.rowcount == 0:
                logger.warning(f"No subscription found to update: {subscription['id']}")
            else:
                logger.info(f"Updated subscription {subscription['id']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error handling subscription webhook: {e}")
        return False

async def handle_invoice_webhook(event: dict, db: AsyncSession) -> bool:
    """Handle invoice-related webhook events"""
    try:
        invoice = event['data']['object']
        event_type = event['type']
        
        logger.info(f"Processing invoice {event_type}: {invoice['id']}")
        
        if not invoice.get('customer_email'):
            logger.warning(f"No customer email in invoice {invoice['id']}")
            return True  # Not an error, just skip
        
        # Find user
        user_query = text("SELECT * FROM omnigatech.site_users WHERE email = :email AND is_active = true")
        user_result = await db.execute(user_query, {"email": invoice['customer_email']})
        user = user_result.first()
        
        if not user:
            logger.warning(f"User not found for invoice email: {invoice['customer_email']}")
            return True  # Not an error for invoice processing
        
        # Record payment in payment_history table
        payment_id = str(uuid.uuid4())
        payment_query = text("""
            INSERT INTO omnigatech.payment_history (
                id, user_id, subscription_id, stripe_invoice_id, stripe_payment_intent_id,
                amount, currency, status, payment_method_type, created_at
            ) VALUES (
                :id, :user_id, :subscription_id, :stripe_invoice_id, :stripe_payment_intent_id,
                :amount, :currency, :status, :payment_method_type, NOW()
            )
        """)
        
        await db.execute(payment_query, {
            "id": payment_id,
            "user_id": user.id,
            "subscription_id": invoice.get('subscription'),
            "stripe_invoice_id": invoice['id'],
            "stripe_payment_intent_id": invoice.get('payment_intent'),
            "amount": invoice['amount_paid'],
            "currency": invoice['currency'],
            "status": 'succeeded' if event_type == 'invoice.payment_succeeded' else 'failed',
            "payment_method_type": 'card'
        })
        
        logger.info(f"Recorded payment for user {user.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error handling invoice webhook: {e}")
        return False

@router.get("/health", response_model=ApiResponse)
async def health_check():
    """Health check endpoint for subscription service"""
    return ApiResponse(
        success=True,
        message="Stripe subscription service is healthy"
    )