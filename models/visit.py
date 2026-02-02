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
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), unique=True)
    
    # Visit Details
    visit_code = Column(String(50), unique=True, nullable=False, index=True)
    visit_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(SQLEnum(VisitStatus), default=VisitStatus.IN_PROGRESS)
    
    # Clinical Details
    chief_complaint = Column(Text)  # Main reason for visit
    symptoms = Column(JSON, default=[])  # List of symptoms
    
    # Vitals (stored as JSON for flexibility)
    vitals = Column(JSON, default={
        # "blood_pressure": "120/80",
        # "temperature": 98.6,
        # "pulse": 72,
        # "weight": 70,
        # "height": 170
    })
    
    # Diagnosis & Treatment
    diagnosis = Column(Text)
    diagnosis_codes = Column(JSON, default=[])  # ICD codes if needed
    treatment_plan = Column(Text)
    prescriptions = Column(JSON, default=[])  # List of medications
    # Example: [{"medicine": "Paracetamol", "dosage": "500mg", "frequency": "Twice daily", "duration": "5 days"}]
    
    # Lab Tests & Procedures
    lab_tests_ordered = Column(JSON, default=[])
    procedures_performed = Column(JSON, default=[])
    
    # Follow-up
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date)
    follow_up_notes = Column(Text)
    
    # Documents
    attachments = Column(JSON, default=[])  # URLs to reports, scans, etc.
    
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