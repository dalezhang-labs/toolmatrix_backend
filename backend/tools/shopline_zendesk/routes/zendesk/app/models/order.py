from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .base import ApiResponse, OrderStatus, PaymentStatus, FulfillmentStatus
from .customer import CustomerAddress

class OrderLineItem(BaseModel):
    id: str
    product_id: str
    variant_id: Optional[str] = None
    title: str
    variant_title: Optional[str] = None
    sku: Optional[str] = None
    quantity: int
    price: float
    total_discount: float = 0.0
    properties: List[Dict[str, Any]] = []
    image_url: Optional[str] = None

class Order(BaseModel):
    id: str
    order_number: str
    email: Optional[str] = None
    phone: Optional[str] = None
    customer_id: Optional[str] = None
    financial_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    order_status: OrderStatus
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    currency: str = "USD"
    total_price: float
    subtotal_price: float
    total_tax: float
    total_discounts: float
    total_shipping: float
    line_items: List[OrderLineItem] = []
    shipping_address: Optional[CustomerAddress] = None
    billing_address: Optional[CustomerAddress] = None
    note: Optional[str] = None
    tags: List[str] = []
    source_name: Optional[str] = None
    gateway: Optional[str] = None
    reference: Optional[str] = None

class OrderFilters(BaseModel):
    status: Optional[OrderStatus] = None
    financial_status: Optional[PaymentStatus] = None
    fulfillment_status: Optional[FulfillmentStatus] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    customer_id: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    min_total: Optional[float] = None
    max_total: Optional[float] = None

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None

class OrderCancellation(BaseModel):
    reason: Optional[str] = None
    notify_customer: bool = True
    restock: bool = True

class RefundRequest(BaseModel):
    amount: float
    reason: str
    notify_customer: bool = True

class OrderResponse(ApiResponse):
    data: Optional[Order] = None

class OrdersResponse(ApiResponse):
    data: Optional[List[Order]] = None 