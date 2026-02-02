from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class LeadSource(str, enum.Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    PHONE = "phone"
    WALK_IN = "walk_in"

class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    CONVERTED = "converted"
    LOST = "lost"

class AILead(Base):
    """
    AI-captured leads from social media and chatbots
    """
    __tablename__ = "ai_leads"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"))  # After conversion
    
    # Lead Info
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255))
    
    # Source
    source = Column(SQLEnum(LeadSource), nullable=False)
    source_details = Column(JSON, default={})  # Platform-specific data
    
    # Lead Details
    message = Column(Text)  # Initial message from lead
    tags = Column(JSON, default=[])  # AI-generated tags
    interested_in = Column(String(200))  # Service/specialty they inquired about
    
    # Status
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW, index=True)
    priority = Column(Integer, default=3)  # 1=High, 3=Low
    
    # AI Processing
    ai_sentiment = Column(String(50))  # positive, neutral, negative
    ai_intent = Column(String(200))  # appointment, inquiry, complaint
    ai_suggested_action = Column(Text)
    
    # Follow-up
    last_contacted_at = Column(DateTime(timezone=True))
    next_follow_up_at = Column(DateTime(timezone=True))
    follow_up_count = Column(Integer, default=0)
    
    # Conversion
    converted_at = Column(DateTime(timezone=True))
    conversion_notes = Column(Text)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))  # Staff member
    
    # Relationships
    patient = relationship("Patient", back_populates="ai_leads")
    appointments = relationship("Appointment", back_populates="ai_lead")
    interactions = relationship("AIInteraction", back_populates="lead", cascade="all, delete-orphan")

class AIInteraction(Base):
    """
    Individual interactions with AI chatbot
    """
    __tablename__ = "ai_interactions"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("ai_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message
    message_type = Column(String(20))  # user, bot
    message_content = Column(Text, nullable=False)
    
    # Metadata
    platform = Column(String(50))  # whatsapp, instagram, facebook
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # AI Processing
    intent_detected = Column(String(200))
    entities_extracted = Column(JSON, default={})
    
    # Relationships
    lead = relationship("AILead", back_populates="interactions")

class AppointmentReminder(Base):
    """
    Automated appointment reminders
    """
    __tablename__ = "appointment_reminders"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False)
    
    # Reminder Details
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    reminder_type = Column(String(20))  # sms, whatsapp, email
    
    # Status
    status = Column(String(20), default="pending")  # pending, sent, failed
    sent_at = Column(DateTime(timezone=True))
    
    # Content
    message_template = Column(String(50))
    message_sent = Column(Text)
    
    # Response tracking
    patient_response = Column(String(20))  # confirmed, rescheduled, cancelled
    response_received_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())