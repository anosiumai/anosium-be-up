from .base import Base, LeadStatus, LeadSource
from sqlalchemy import Column, Float, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, JSON, Enum as SQLEnum
from datetime import datetime


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    
    # Contact Info
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255))
    
    # Lead Details
    source = Column(SQLEnum(LeadSource), nullable=False)
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW)
    
    # AI Interaction
    initial_message = Column(Text)
    conversation_history = Column(JSON, default=[])  # [{role, message, timestamp}]
    ai_responses = Column(Integer, default=0)
    
    # Qualification
    intent = Column(String(255))  # appointment, inquiry, emergency
    preferred_doctor = Column(String(255))
    preferred_date = Column(DateTime)
    service_interest = Column(String(255))
    
    # Conversion
    converted_to_patient = Column(Boolean, default=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    converted_at = Column(DateTime)
    
    # Follow-up
    last_contacted = Column(DateTime)
    next_follow_up = Column(DateTime)
    follow_up_count = Column(Integer, default=0)
    
    # Metadata
    metadata = Column(JSON, default={})  # platform_data, tags, custom_fields
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_lead_clinic_status', 'clinic_id', 'status'),
        Index('idx_lead_source_date', 'source', 'created_at'),
        Index('idx_lead', 'clinic_id', 'next_follow_up'),
    )


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    
    # Interaction
    platform = Column(String(50), nullable=False)  # whatsapp, instagram, facebook
    message_type = Column(String(50))  # text, image, voice
    user_message = Column(Text)
    ai_response = Column(Text)
    
    # Context
    intent_detected = Column(String(100))
    entities_extracted = Column(JSON, default={})
    confidence_score = Column(Float)
    
    # Action taken
    action_taken = Column(String(100))  # appointment_booked, lead_created, info_provided
    
    # Performance
    response_time_ms = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_interaction_clinic_date', 'clinic_id', 'created_at'),
        Index('idx_interaction_lead', 'lead_id'),
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Trigger
    trigger_type = Column(String(50), nullable=False)  # new_lead, missed_appointment, payment_due
    trigger_conditions = Column(JSON, default={})
    
    # Action
    action_type = Column(String(50), nullable=False)  # send_message, create_task, send_email
    action_config = Column(JSON, default={})
    
    # Schedule
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    
    # Stats
    execution_count = Column(Integer, default=0)
    last_executed = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_automation_clinic_active', 'clinic_id', 'is_active'),
    )