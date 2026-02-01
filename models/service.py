from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Index, Text, ForeignKey
from datetime import datetime

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    tax_percentage = Column(Float, default=0.0)
    
    # Categorization
    category = Column(String(100))
    is_package = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_service_clinic_active', 'clinic_id', 'is_active'),
    )