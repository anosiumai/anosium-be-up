from .base import Base, SubscriptionTier, SubscriptionStatus
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Enum as SQLEnum, Index, UniqueConstraint
from datetime import datetime

class Clinic(Base):
    __tablename__ = "clinics"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(20))
    address = Column(Text)
    
    # Branding
    logo_url = Column(String(500))
    primary_color = Column(String(7), default="#3B82F6")
    secondary_color = Column(String(7), default="#10B981")
    
    # Subscription
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    subscription_start = Column(DateTime, default=datetime.utcnow)
    subscription_end = Column(DateTime)
    
    # Features enabled
    features = Column(JSON, default={
        "ai_automation": False,
        "advanced_billing": False,
        "analytics": False,
        "whatsapp_integration": False,
        "max_doctors": 2,
        "max_patients": 50
    })
    
    # AI Configuration
    ai_config = Column(JSON, default={
        "enabled": False,
        "auto_respond": False,
        "lead_capture": False,
        "appointment_booking": False
    })
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (handled via back_populates in other models)
    __table_args__ = (
        Index('idx_clinic_active', 'is_active', 'subscription_status'),
    )