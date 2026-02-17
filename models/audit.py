"""
Audit Models
SQLAlchemy models for audit logging and HIPAA compliance
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from core.database import Base


class AuditAction(str, enum.Enum):
    """Audit action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    SHARE = "share"
    DOWNLOAD = "download"
    PRINT = "print"


class AuditLog(Base):
    """Audit log for tracking all system actions"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    action = Column(Enum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(Integer, nullable=False, index=True)
    
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    changes_summary = Column(Text, nullable=True)
    
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # ✅ FIX: Add viewonly=True to prevent requiring back_populates
    tenant = relationship("Tenant", foreign_keys=[tenant_id], viewonly=True)
    user = relationship("User", foreign_keys=[user_id], viewonly=True)


class DataAccessLog(Base):
    """Log for tracking access to sensitive patient data (HIPAA compliance)"""
    __tablename__ = "data_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    
    access_type = Column(String(50), nullable=False)
    accessed_fields = Column(JSON, nullable=True)
    purpose = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # ✅ FIX: Add viewonly=True to prevent requiring back_populates
    tenant = relationship("Tenant", foreign_keys=[tenant_id], viewonly=True)
    user = relationship("User", foreign_keys=[user_id], back_populates="data_access_logs")
    patient = relationship("Patient", foreign_keys=[patient_id], viewonly=True)