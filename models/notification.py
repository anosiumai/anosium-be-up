from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean, JSON, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class NotificationType(str, enum.Enum):
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    PAYMENT_DUE = "payment_due"
    PAYMENT_RECEIVED = "payment_received"
    FOLLOW_UP = "follow_up"
    MISSED_APPOINTMENT = "missed_appointment"
    PRESCRIPTION_READY = "prescription_ready"
    LAB_RESULTS = "lab_results"
    MARKETING = "marketing"
    SYSTEM = "system"

class NotificationChannel(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"
    PUSH = "push"

class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"

class Notification(Base):
    """
    Unified notification system for all channels
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Recipient
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    
    # Notification Details
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    
    # Content
    subject = Column(String(500))
    message = Column(Text, nullable=False)
    template_id = Column(String(100))  # Reference to template
    template_variables = Column(JSON)  # Variables used in template
    
    # Delivery
    recipient_email = Column(String(255))
    recipient_phone = Column(String(20))
    
    # Status
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, index=True)
    
    # Tracking
    scheduled_for = Column(DateTime(timezone=True), index=True)
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    
    # Error Handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # External IDs
    external_id = Column(String(200))  # ID from SMS/Email provider
    
    # Metadata
    meta = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    patient = relationship("Patient")

class NotificationTemplate(Base):
    """
    Reusable message templates
    """
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Template Details
    code = Column(String(100), nullable=False, index=True)  # e.g., APPT_REMINDER_24H
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    
    # Content (supports variables like {patient_name}, {appointment_time})
    subject_template = Column(String(500))
    body_template = Column(Text, nullable=False)
    
    # Language Support
    language = Column(String(10), default="en")
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class NotificationPreference(Base):
    """
    User notification preferences
    """
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), unique=True)
    
    # Channel Preferences
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    whatsapp_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    
    # Type Preferences (JSON for flexibility)
    enabled_types = Column(JSON, default={
        "appointment_reminder": True,
        "payment_due": True,
        "marketing": False
    })
    
    # Quiet Hours
    quiet_hours_start = Column(Time)
    quiet_hours_end = Column(Time)
    timezone = Column(String(50), default="UTC")
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    patient = relationship("Patient")