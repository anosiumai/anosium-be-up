from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
from datetime import datetime, timedelta

class RefreshToken(Base):
    """
    JWT refresh tokens for secure authentication
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token Details
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Device/Session Info
    device_id = Column(String(200))
    device_name = Column(String(200))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Status
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True))
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")

class LoginAttempt(Base):
    """
    Track failed login attempts for security
    """
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    
    # Attempt Details
    success = Column(Boolean, default=False)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(String(500))
    
    # Error Details
    failure_reason = Column(String(200))  # invalid_password, account_locked, etc.
    
    # Timestamp
    attempted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class PasswordResetToken(Base):
    """
    Secure password reset tokens
    """
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True))
    
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")

class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class TwoFactorAuth(Base):
    """
    2FA for enhanced security (optional)
    """
    __tablename__ = "two_factor_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # 2FA Method
    method = Column(String(20), default="totp")  # totp, sms, email
    secret = Column(String(200))  # Encrypted TOTP secret
    
    # Backup Codes
    backup_codes = Column(JSON)  # Encrypted list of backup codes
    
    # Status
    is_enabled = Column(Boolean, default=False)
    enabled_at = Column(DateTime(timezone=True))
    
    # Last Verification
    last_verified_at = Column(DateTime(timezone=True))
    
    user = relationship("User")