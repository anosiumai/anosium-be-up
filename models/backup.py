from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class BackupJob(Base):
    """
    Automated backup tracking for disaster recovery
    """
    __tablename__ = "backup_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    
    # Backup Details
    backup_type = Column(String(50), nullable=False)  # full, incremental, differential
    backup_location = Column(String(500), nullable=False)  # S3, local, etc.
    
    # Status
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    
    # Size & Duration
    size_bytes = Column(BigInteger)
    duration_seconds = Column(Integer)
    
    # Verification
    checksum = Column(String(200))
    verified = Column(Boolean, default=False)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Error Handling
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)