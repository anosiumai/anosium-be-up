from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime
from models.tenant import SubscriptionTier, SubscriptionStatus

class TenantBase(BaseModel):
    """Base tenant schema"""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    
    class Config:
        from_attributes = True

class TenantCreate(TenantBase):
    """Create tenant schema"""
    slug: str = Field(..., pattern=r'^[a-z0-9-]+$', min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    admin_first_name: str = Field(..., min_length=2)
    admin_last_name: str = Field(..., min_length=2)
    
    @validator('slug')
    def validate_slug(cls, v):
        if v in ['admin', 'api', 'app', 'www', 'dashboard']:
            raise ValueError('Reserved slug')
        return v.lower()

class TenantUpdate(BaseModel):
    """Update tenant schema"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    settings: Optional[Dict[str, Any]] = None

class SubscriptionUpdate(BaseModel):
    """Update subscription"""
    subscription_tier: SubscriptionTier
    subscription_status: Optional[SubscriptionStatus] = None
    enabled_features: Optional[Dict[str, Any]] = None

class TenantInDB(TenantBase):
    """Tenant from database"""
    id: int
    slug: str
    subscription_tier: SubscriptionTier
    subscription_status: SubscriptionStatus
    subscription_start_date: Optional[datetime]
    subscription_end_date: Optional[datetime]
    enabled_features: Dict[str, Any]
    logo_url: Optional[str]
    primary_color: str
    settings: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class Tenant(TenantInDB):
    """Public tenant schema"""
    pass

class TenantWithStats(Tenant):
    """Tenant with statistics"""
    total_patients: int = 0
    total_doctors: int = 0
    total_appointments: int = 0
    monthly_revenue: int = 0
    active_users: int = 0