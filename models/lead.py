from .base import Base, LeadStatus, LeadSource
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, JSON, Enum as SQLEnum
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
    next_follow = Column(DateTime)  # This is the actual column name
    follow_up_count = Column(Integer, default=0)
    
    # Metadata
    custom_metadata = Column(JSON, default={})  # platform_data, tags, custom_fields
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_lead_clinic_status', 'clinic_id', 'status'),
        Index('idx_lead_source_date', 'source', 'created_at'),
        # Fixed: changed 'next_follow_up' to 'next_follow' to match actual column name
        Index('idx_lead_follow_up', 'clinic_id', 'next_follow'),
    )