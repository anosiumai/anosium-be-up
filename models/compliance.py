from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class ConsentType(str, enum.Enum):
    TREATMENT = "treatment"
    DATA_PROCESSING = "data_processing"
    MARKETING = "marketing"
    DATA_SHARING = "data_sharing"
    RESEARCH = "research"

class PatientConsent(Base):
    """
    Patient consent tracking for GDPR compliance
    """
    __tablename__ = "patient_consents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Consent Details
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    consent_given = Column(Boolean, nullable=False)
    
    # Documentation
    consent_text = Column(Text)  # What they consented to
    consent_version = Column(String(20))  # Version of consent form
    
    # Signature
    signature_data = Column(Text)  # Base64 signature or digital signature
    ip_address = Column(String(45))
    
    # Timing
    consented_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    withdrawn_at = Column(DateTime(timezone=True))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    patient = relationship("Patient")

class DataRetentionPolicy(Base):
    """
    Data retention policies for compliance
    """
    __tablename__ = "data_retention_policies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Policy Details
    data_type = Column(String(100), nullable=False)  # patient_record, appointment, invoice
    retention_period_days = Column(Integer, nullable=False)
    
    # Actions
    action_on_expiry = Column(String(50), nullable=False)  # archive, anonymize, delete
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class DataDeletionRequest(Base):
    """
    GDPR Right to be Forgotten requests
    """
    __tablename__ = "data_deletion_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    
    # Request Details
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    reason = Column(Text)
    
    # Status
    status = Column(String(50), default="pending")  # pending, approved, rejected, completed
    
    # Processing
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Legal Hold
    legal_hold = Column(Boolean, default=False)
    legal_hold_reason = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())