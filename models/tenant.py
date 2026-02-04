from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"

class Tenant(Base):
    """
    Core tenant model - each clinic is a tenant
    All other models will reference this for multi-tenancy
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Contact & Location
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    
    # Subscription Management
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    subscription_start_date = Column(DateTime(timezone=True))
    subscription_end_date = Column(DateTime(timezone=True))
    
    # Feature Flags (JSON for flexibility)
    enabled_features = Column(JSON, default={
        "ai_chatbot": False,
        "advanced_billing": False,
        "analytics": False,
        "max_doctors": 5,
        "max_patients": 100
    })
    
    # Branding
    logo_url = Column(String(500))
    primary_color = Column(String(7), default="#3B82F6")
    settings = Column(JSON, default={})  # Clinic-specific configurations
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ✅ RELATIONSHIPS - ONLY THE ORIGINAL ONES
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    patients = relationship("Patient", back_populates="tenant", cascade="all, delete-orphan")
    doctors = relationship("Doctor", back_populates="tenant", cascade="all, delete-orphan")
    departments = relationship("Department", back_populates="tenant", cascade="all, delete-orphan")