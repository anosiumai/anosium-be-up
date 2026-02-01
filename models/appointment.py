from .base import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, Text
from datetime import datetime

class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    appointment_number = Column(String(50), unique=True, index=True, nullable=False)
    
    appointment_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    
    # Status
    status = Column(String(50), default="scheduled")  # scheduled, confirmed, completed, cancelled, no_show
    
    # Details
    reason = Column(Text)
    notes = Column(Text)
    
    # AI Related
    booked_via_ai = Column(Boolean, default=False)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    
    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_appointment_clinic_date', 'clinic_id', 'appointment_date'),
        Index('idx_appointment_doctor_date', 'doctor_id', 'appointment_date'),
        Index('idx_appointment_status', 'status', 'clinic_id'),
    )