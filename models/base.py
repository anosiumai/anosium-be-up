from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index, JSON, Enum as SQLEnum, UniqueConstraint
from datetime import datetime
import enum

Base = declarative_base()

# ==================== ENUMS ====================
class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    CLINIC_ADMIN = "clinic_admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF = "staff"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"

class LeadSource(str, enum.Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    WALK_IN = "walk_in"