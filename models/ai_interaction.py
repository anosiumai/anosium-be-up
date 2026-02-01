from .base import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, JSON, Float
from datetime import datetime

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