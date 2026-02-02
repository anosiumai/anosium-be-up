from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func 
from core.database import Base
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"  # Owner company
    CLINIC_ADMIN = "clinic_admin"  # Clinic owner/manager
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF = "staff"
    ACCOUNTANT = "accountant"

class User(Base):
    """
    Unified user model for all roles
    Links to Doctor model if role is DOCTOR
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    
    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    avatar_url = Column(String(500))
    
    # Permissions (JSON for granular control)
    permissions = Column(JSON, default={})
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    doctor_profile = relationship("Doctor", back_populates="user", uselist=False)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"