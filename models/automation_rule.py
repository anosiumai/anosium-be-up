from .base import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, JSON
from datetime import datetime

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