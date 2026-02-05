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

class Package(Base):
    """
    Service packages/bundles with discounted pricing
    Example: Health Checkup Package, Vaccination Package
    """
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Package Details
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, index=True)
    description = Column(Text)
    
    # Pricing
    package_price = Column(Integer, nullable=False)  # Discounted price in cents/paise
    discount_percentage = Column(Integer, default=0)
    
    # Validity
    validity_days = Column(Integer, default=365)  # How long package is valid
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", viewonly=True)
    package_services = relationship("PackageService", back_populates="package", cascade="all, delete-orphan")


class PackageService(Base):
    """
    Junction table linking packages to services
    """
    __tablename__ = "package_services"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    
    # Relationships
    package = relationship("Package", back_populates="package_services")
    service = relationship("Service", back_populates="package_services")