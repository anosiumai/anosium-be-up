from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Department(Base):
    """
    Hospital/Clinic departments
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(200), nullable=False)
    code = Column(String(20), nullable=False)  # e.g., CARDIO, NEURO
    description = Column(Text)
    
    # Head of Department
    head_doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="SET NULL"))
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="departments")
    doctors = relationship("Doctor", back_populates="department", foreign_keys="Doctor.department_id")
    head_doctor = relationship("Doctor", foreign_keys=[head_doctor_id], post_update=True)
    services = relationship("Service", back_populates="department")