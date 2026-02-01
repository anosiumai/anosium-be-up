from .base import Base, UserRole
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20))
    role = Column(SQLEnum(UserRole), nullable=False)  # Now SQLEnum is properly imported
    
    # Doctor specific
    specialization = Column(String(255))
    license_number = Column(String(100))
    
    # Status
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_clinic_role', 'clinic_id', 'role', 'is_active'),
        UniqueConstraint('clinic_id', 'email', name='uq_clinic_user_email'),
    )