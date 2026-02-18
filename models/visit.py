from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum, Date, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class VisitStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PENDING_PAYMENT = "pending_payment"

class Visit(Base):
    """
    Patient visit records with diagnoses and treatments
    """
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # FIX: Removed unique=True. One appointment can have multiple visits (follow-ups, splits).
    # Added index=True for query performance.
    appointment_id = Column(
        Integer, 
        ForeignKey("appointments.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Visit Details
    visit_code = Column(String(50), unique=True, nullable=False, index=True)
    visit_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(SQLEnum(VisitStatus), default=VisitStatus.IN_PROGRESS)
    
    # Clinical Details
    chief_complaint = Column(Text)  # Main reason for visit
    
    # FIX: Mutable default fixed. Use callable `list` instead of instance `[]`.
    symptoms = Column(JSON, default=list)  
    
    # Vitals (stored as JSON for flexibility)
    # FIX: Mutable default fixed. Use callable `dict` instead of instance `{}`.
    vitals = Column(JSON, default=dict)
    
    # Diagnosis & Treatment
    diagnosis = Column(Text)
    diagnosis_codes = Column(JSON, default=list)
    treatment_plan = Column(Text)
    # FIX: Mutable default fixed.
    prescriptions = Column(JSON, default=list)
    
    # Lab Tests & Procedures
    # FIX: Mutable default fixed.
    lab_tests_ordered = Column(JSON, default=list)
    procedures_performed = Column(JSON, default=list)
    
    # Follow-up
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date)
    follow_up_notes = Column(Text)
    
    # Documents
    # FIX: Mutable default fixed.
    attachments = Column(JSON, default=list)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    patient = relationship("Patient", back_populates="visits")
    doctor = relationship("Doctor", back_populates="visits")
    appointment = relationship("Appointment", back_populates="visit")
    visit_services = relationship("VisitService", back_populates="visit", cascade="all, delete-orphan")
    invoice = relationship("Invoice", back_populates="visit", uselist=False)