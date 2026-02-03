from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import secrets

from core.config import settings
from core.security import verify_password, get_password_hash
from models.user import User
from models.security import RefreshToken, LoginAttempt, PasswordResetToken
from repositories.user import UserRepository
from schemas.user import UserCreate, Token, TokenData
from services.base_service import BaseService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService(BaseService):
    """Authentication and authorization service"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.user_repo = UserRepository(db)
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.user_repo.get_by_email(email)
        
        # Log login attempt
        self._log_login_attempt(email, user is not None, "invalid_credentials" if not user else None)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            self._log_login_attempt(email, False, "invalid_password")
            return None
        
        # Check if account is locked
        if not user.is_active:
            self._log_login_attempt(email, False, "account_locked")
            return None
        
        return user
    
    def create_user(self, user_in: UserCreate) -> User:
        """Create new user"""
        # Check if email exists
        if self.user_repo.check_email_exists(user_in.email):
            raise ValueError("Email already registered")
        
        # Hash password
        hashed_password = get_password_hash(user_in.password)
        
        # Create user
        user_data = user_in.dict(exclude={'password'})
        user_data['hashed_password'] = hashed_password
        
        user = self.user_repo.create(user_data)
        self.commit()
        
        # Send verification email (implement separately)
        # self._send_verification_email(user)
        
        return user
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token"""
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta
        
        to_encode = {
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "role": user.role.value,
            "email": user.email,
            "exp": expire,
            "type": "access"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, user: User) -> str:
        """Create refresh token"""
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.utcnow() + expires_delta
        
        # Generate random token
        token = secrets.token_urlsafe(32)
        
        # Store in database
        refresh_token = RefreshToken(
            user_id=user.id,
            token=token,
            expires_at=expire
        )
        
        self.db.add(refresh_token)
        self.commit()
        
        return token
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh access token using refresh token"""
        # Find refresh token
        token_obj = self.db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        ).first()
        
        if not token_obj:
            raise ValueError("Invalid or expired refresh token")
        
        # Get user
        user = self.user_repo.get(token_obj.user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        
        # Update last used
        token_obj.last_used_at = datetime.utcnow()
        self.commit()
        
        # Create new access token
        return self.create_access_token(user)
    
    def revoke_user_tokens(self, user_id: int):
        """Revoke all refresh tokens for a user"""
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({
            'is_revoked': True,
            'revoked_at': datetime.utcnow()
        })
        
        self.commit()
    
    def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        self.user_repo.update_last_login(user_id)
        self.commit()
    
    def create_password_reset_token(self, email: str) -> Optional[str]:
        """Create password reset token"""
        user = self.user_repo.get_by_email(email)
        if not user:
            return None
        
        # Generate token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Store token
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        
        self.db.add(reset_token)
        self.commit()
        
        # Send email (implement separately)
        # self._send_password_reset_email(user, token)
        
        return token
    
    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token"""
        # Find valid token
        token_obj = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not token_obj:
            return False
        
        # Update password
        user = self.user_repo.get(token_obj.user_id)
        if not user:
            return False
        
        hashed_password = get_password_hash(new_password)
        self.user_repo.update(user.id, {'hashed_password': hashed_password})
        
        # Mark token as used
        token_obj.is_used = True
        token_obj.used_at = datetime.utcnow()
        
        self.commit()
        
        return True
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        
        # Verify old password
        if not verify_password(old_password, user.hashed_password):
            return False
        
        # Update password
        hashed_password = get_password_hash(new_password)
        self.user_repo.update(user_id, {'hashed_password': hashed_password})
        
        self.commit()
        
        return True
    
    def verify_email(self, token: str) -> bool:
        """Verify user email"""
        # Implement email verification logic
        # This would involve checking a verification token and updating user.is_verified
        pass
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.user_repo.get_by_email(email)
    
    def _log_login_attempt(self, email: str, success: bool, failure_reason: Optional[str] = None):
        """Log login attempt"""
        login_attempt = LoginAttempt(
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address="0.0.0.0",  # Get from request context
            attempted_at=datetime.utcnow()
        )
        
        self.db.add(login_attempt)
        self.db.flush()