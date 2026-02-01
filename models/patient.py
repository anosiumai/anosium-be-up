from .base import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint, JSON
from datetime import datetime

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    
    patient_code = Column(String(50), index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(20), nullable=False)
    date_of_birth = Column(DateTime)
    gender = Column(String(20))
    address = Column(Text)
    
    # Medical
    blood_group = Column(String(5))
    allergies = Column(Text)
    medical_history = Column(JSON, default=[])
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_patient_clinic_phone', 'clinic_id', 'phone'),
        Index('idx_patient_clinic_email', 'clinic_id', 'email'),
        UniqueConstraint('clinic_id', 'patient_code', name='uq_clinic_patient_code'),
    )