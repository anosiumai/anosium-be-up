# models/appointment.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean, Date, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"

class AppointmentType(str, enum.Enum):
    NEW_CONSULTATION = "new_consultation"
    FOLLOW_UP = "follow_up"
    EMERGENCY = "emergency"
    ROUTINE_CHECKUP = "routine_checkup"

class Appointment(Base):
    """
    Appointment scheduling and management
    """
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Appointment Details
    appointment_code = Column(String(50), unique=True, nullable=False, index=True)
    appointment_date = Column(Date, nullable=False, index=True)
    appointment_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, default=30)
    
    appointment_type = Column(SQLEnum(AppointmentType), default=AppointmentType.NEW_CONSULTATION)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, index=True)
    
    # Details
    reason = Column(Text)
    notes = Column(Text)  # Internal notes
    
    # AI Integration
    booked_via_ai = Column(Boolean, default=False)
    ai_lead_id = Column(Integer, ForeignKey("ai_leads.id", ondelete="SET NULL"))
    
    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    
    # Tracking
    checked_in_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    visit = relationship("Visit", back_populates="appointment", uselist=False)
    ai_lead = relationship("AILead", back_populates="appointments")