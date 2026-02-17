from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Time, JSON, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Doctor(Base):
    """
    Doctor profiles with specializations and availability
    """
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"))
    
    # Professional Info
    doctor_code = Column(String(50), unique=True, nullable=False, index=True)
    specialization = Column(String(200), nullable=False)
    qualification = Column(String(500))  # e.g., MBBS, MD
    license_number = Column(String(100))
    experience_years = Column(Integer)
    
    # Consultation
    consultation_fee = Column(Integer, default=0)  # In cents/paise
    average_consultation_time = Column(Integer, default=30)  # Minutes
    
    # Availability (JSON structure for flexibility)
    # Example: {"monday": {"start": "09:00", "end": "17:00", "slots": 16}, ...}
    availability_schedule = Column(JSON, default={})
    
    # Status
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    joined_date = Column(Date)
    bio = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="doctors", foreign_keys=[tenant_id])
    user = relationship("User", back_populates="doctor_profile")
    department = relationship("Department", back_populates="doctors", foreign_keys=[department_id])
    appointments = relationship("Appointment", back_populates="doctor")
    visits = relationship("Visit", back_populates="doctor")