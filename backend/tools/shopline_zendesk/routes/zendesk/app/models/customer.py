from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime
from .base import ApiResponse

class CustomerAddress(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    city: str
    province: Optional[str] = None
    country: str
    zip: str
    phone: Optional[str] = None

class Customer(BaseModel):
    id: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    accepts_marketing: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    orders_count: int = 0
    total_spent: float = 0.0
    tags: List[str] = []
    note: Optional[str] = None
    verified_email: bool = False
    default_address: Optional[CustomerAddress] = None
    addresses: List[CustomerAddress] = []

class CustomerFilters(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None

class CustomerResponse(ApiResponse):
    data: Optional[Customer] = None

class CustomersResponse(ApiResponse):
    data: Optional[List[Customer]] = None 