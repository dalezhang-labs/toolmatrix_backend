"""
Stripe Plan Configuration
Pre-defined price IDs for standard subscription plans
"""

# Standard subscription plans with fixed Stripe Price IDs
STANDARD_PLANS = {
    "Basic": {
        "price_id": None,  # Will be set after creating in Stripe
        "product_id": None,  # Will be set after creating in Stripe
        "amount": 700,  # $7.00 in cents
        "currency": "usd",
        "interval": "month",
        "description": "Basic Plan - Perfect for individuals and small teams",
        "features": [
            "Up to 100 products",
            "Basic analytics",
            "Email support"
        ]
    },
    "Professional": {
        "price_id": None,  # Will be set after creating in Stripe
        "product_id": None,  # Will be set after creating in Stripe
        "amount": 1700,  # $17.00 in cents
        "currency": "usd",
        "interval": "month",
        "description": "Professional Plan - For growing businesses",
        "features": [
            "Unlimited products",
            "Advanced analytics",
            "Priority email support",
            "API access"
        ]
    },
    "Enterprise": {
        "price_id": None,  # Will be set after creating in Stripe
        "product_id": None,  # Will be set after creating in Stripe
        "amount": 3700,  # $37.00 in cents
        "currency": "usd",
        "interval": "month",
        "description": "Enterprise Plan - For large organizations",
        "features": [
            "Everything in Professional",
            "Custom integrations",
            "Dedicated support",
            "SLA guarantee",
            "Advanced security features"
        ]
    }
}

def get_plan_by_name(plan_name: str):
    """Get plan configuration by name"""
    return STANDARD_PLANS.get(plan_name)

def get_plan_by_amount(amount: int, interval: str = "month"):
    """Get plan configuration by amount and interval"""
    for name, plan in STANDARD_PLANS.items():
        if plan["amount"] == amount and plan["interval"] == interval:
            return {"name": name, **plan}
    return None

def is_standard_plan(plan_name: str, amount: int = None):
    """Check if a plan is a standard plan"""
    if plan_name not in STANDARD_PLANS:
        return False
    if amount is not None:
        return STANDARD_PLANS[plan_name]["amount"] == amount
    return True