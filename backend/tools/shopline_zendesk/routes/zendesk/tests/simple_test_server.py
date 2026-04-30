#!/usr/bin/env python3
"""Simple test server for customer search API"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test data
test_customers = [
    {
        "id": "cust_1",
        "email": "joseph.manneh@example.com",
        "first_name": "Joseph",
        "last_name": "Manneh",
        "phone": "8185641059",
        "orders_count": 5,
        "total_spent": 1098.39,
        "created_at": "2024-01-15T10:00:00Z"
    },
    {
        "id": "cust_2",
        "email": "customer1098394@example.com",
        "first_name": "Order",
        "last_name": "Customer",
        "phone": "+1234567890",
        "orders_count": 1,
        "total_spent": 394.00,
        "created_at": "2024-02-20T14:30:00Z",
        "order_id": "1098394"
    }
]

@app.get("/api/customers/search")
async def search_customers(
    email: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    phone: Optional[str] = Query(None)
):
    """Search customers by various criteria"""
    
    results = []
    
    for customer in test_customers:
        # Check if customer matches search criteria
        if order_id and order_id == "1098394":
            # Return customer associated with this order
            if customer.get("order_id") == "1098394":
                results.append(customer)
        elif first_name and last_name:
            if (customer["first_name"].lower() == first_name.lower() and 
                customer["last_name"].lower() == last_name.lower()):
                results.append(customer)
        elif phone:
            # Clean phone number for comparison
            clean_phone = ''.join(filter(str.isdigit, phone))
            customer_phone = ''.join(filter(str.isdigit, customer.get("phone", "")))
            if clean_phone and customer_phone and clean_phone in customer_phone:
                results.append(customer)
        elif email:
            if customer["email"].lower() == email.lower():
                results.append(customer)
    
    return {
        "success": True,
        "data": results,
        "total": len(results)
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "customer-search-test"}

if __name__ == "__main__":
    print("Starting test server on http://localhost:5002")
    print("Test cases ready:")
    print("1. Order ID: 1098394")
    print("2. Name: Joseph Manneh")
    print("3. Phone: 8185641059")
    uvicorn.run(app, host="0.0.0.0", port=5002)