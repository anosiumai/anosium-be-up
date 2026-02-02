from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class ServiceType(str, enum.Enum):
    CONSULTATION = "consultation"
    PROCEDURE = "procedure"
    LAB_TEST = "lab_test"
    IMAGING = "imaging"
    SURGERY = "surgery"
    THERAPY = "therapy"
    PACKAGE = "package"

class Service(Base):
    """
    Hospital services with pricing
    """
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"))
    
    # Service Info
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    
    # Pricing
    base_price = Column(Integer, nullable=False)  # In cents/paise
    tax_percentage = Column(Integer, default=0)  # e.g., 18 for 18%
    
    # Duration (for scheduling)
    estimated_duration_minutes = Column(Integer)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    department = relationship("Department", back_populates="services")
    visit_services = relationship("VisitService", back_populates="service")
    package_services = relationship("PackageService", back_populates="service")