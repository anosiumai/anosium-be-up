from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any

class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class ClinicBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    secondary_color: str = "#10B981"

class ClinicCreate(ClinicBase):
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE

class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    subscription_tier: Optional[SubscriptionTier] = None
    features: Optional[Dict[str, Any]] = None
    ai_config: Optional[Dict[str, Any]] = None

class ClinicResponse(ClinicBase):
    id: int
    clinic_code: str
    subscription_tier: str
    subscription_status: str
    features: Dict[str, Any]
    ai_config: Dict[str, Any]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ClinicStats(BaseModel):
    total_patients: int
    total_appointments: int
    total_revenue: float
    pending_invoices: int
    active_leads: int
    conversion_rate: float
    
class RevenueReport(BaseModel):
    """Comprehensive revenue report schema for billing analytics"""
    
    # Identification & Time Period
    clinic_id: int
    from_date: datetime
    to_date: datetime
    
    # Revenue Totals
    total_revenue: float = 0.0
    paid_revenue: float = 0.0
    pending_revenue: float = 0.0
    overdue_revenue: float = 0.0
    cancelled_revenue: float = 0.0
    
    # Invoice Counts
    total_invoices: int = 0
    paid_invoices: int = 0
    pending_invoices: int = 0
    overdue_invoices: int = 0
    cancelled_invoices: int = 0
    partial_invoices: int = 0
    
    # Payment Method Breakdown
    cash_payments: float = 0.0
    card_payments: float = 0.0
    online_payments: float = 0.0
    insurance_payments: float = 0.0
    other_payments: float = 0.0
    
    # Financial Metrics
    total_tax_collected: float = 0.0
    total_discounts: float = 0.0
    net_revenue: float = 0.0
    
    # Averages
    average_invoice_amount: float = 0.0
    average_payment_amount: float = 0.0
    
    # Performance Metrics
    collection_rate: float = 0.0
    payment_success_rate: float = 0.0
    
    # Optional Detailed Breakdowns
    top_services: Optional[List[Dict[str, Any]]] = None
    daily_breakdown: Optional[List[Dict[str, Any]]] = None
    payment_method_breakdown: Optional[Dict[str, float]] = None
    
    # Report Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True