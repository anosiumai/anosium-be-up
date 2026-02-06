from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import logging

# ✅ Import from centralized security module
from core.config import settings
from core.security import verify_password, get_password_hash, validate_password_strength
from models.user import User
from models.security import RefreshToken, LoginAttempt, PasswordResetToken
from repositories.user import UserRepository
from schemas.user import UserCreate
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class AuthService(BaseService):
    """Authentication and authorization service"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.user_repo = UserRepository(db)
    
    def authenticate_user(self, email: str, password: str, ip_address: str = "0.0.0.0") -> Optional[User]:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: Plain text password
            ip_address: Request IP address for logging
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.user_repo.get_by_email(email)
        
        if not user:
            self._log_login_attempt(email, False, "user_not_found", ip_address)
            return None
        
        if not verify_password(password, user.hashed_password):
            self._log_login_attempt(email, False, "invalid_password", ip_address)
            return None
        
        if not user.is_active:
            self._log_login_attempt(email, False, "account_inactive", ip_address)
            return None
        
        # ✅ Successful login
        self._log_login_attempt(email, True, None, ip_address)
        return user
    
    def create_user(self, user_in: UserCreate) -> User:
        """
        Create new user with password validation
        
        Args:
            user_in: User creation schema
            
        Returns:
            Created user object
            
        Raises:
            ValueError: If email exists or password is weak
        """
        # Check if email exists
        if self.user_repo.check_email_exists(user_in.email):
            raise ValueError("Email already registered")
        
        # ✅ Validate password strength
        is_valid, error_message = validate_password_strength(user_in.password)
        if not is_valid:
            raise ValueError(error_message)
        
        # Hash password
        hashed_password = get_password_hash(user_in.password)
        
        # Create user
        user_data = user_in.dict(exclude={'password'})
        user_data['hashed_password'] = hashed_password
        
        user = self.user_repo.create(user_data)
        self.commit()
        
        logger.info(f"New user created: {user.email} (ID: {user.id})")
        
        return user
    
    def create_access_token(self, user: User) -> str:
        """
        Create JWT access token
        
        Args:
            user: User object
            
        Returns:
            JWT access token string
        """
        from jose import jwt
        
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta
        
        to_encode = {
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "role": user.role.value,
            "email": user.email,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    def create_refresh_token(
        self,
        user: User,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Create database-stored refresh token
        
        Args:
            user: User object
            device_id: Optional device identifier
            device_name: Optional device name
            ip_address: Optional IP address
            user_agent: Optional user agent string
            
        Returns:
            Refresh token string
        """
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.utcnow() + expires_delta
        
        # Generate cryptographically secure random token
        token = secrets.token_urlsafe(32)
        
        # Store in database
        refresh_token = RefreshToken(
            user_id=user.id,
            token=token,
            expires_at=expire,
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(refresh_token)
        self.commit()
        
        logger.info(f"Refresh token created for user {user.id}")
        
        return token
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token string
            
        Returns:
            New access token
            
        Raises:
            ValueError: If refresh token is invalid or expired
        """
        # Find valid refresh token
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
        
        # Update last used timestamp
        token_obj.last_used_at = datetime.utcnow()
        self.commit()
        
        # Create new access token
        return self.create_access_token(user)
    
    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a specific refresh token
        
        Args:
            refresh_token: Token to revoke
            
        Returns:
            True if revoked, False if not found
        """
        token_obj = self.db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.is_revoked == False
        ).first()
        
        if not token_obj:
            return False
        
        token_obj.is_revoked = True
        token_obj.revoked_at = datetime.utcnow()
        self.commit()
        
        return True
    
    def revoke_user_tokens(self, user_id: int):
        """
        Revoke all refresh tokens for a user (logout from all devices)
        
        Args:
            user_id: User ID
        """
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({
            'is_revoked': True,
            'revoked_at': datetime.utcnow()
        })
        
        self.commit()
        logger.info(f"All refresh tokens revoked for user {user_id}")
    
    def update_last_login(self, user_id: int):
        """
        Update user's last login timestamp
        
        Args:
            user_id: User ID
        """
        self.user_repo.update_last_login(user_id)
        self.commit()
    
    def create_password_reset_token(self, email: str) -> Optional[str]:
        """
        Create password reset token
        
        Args:
            email: User email
            
        Returns:
            Reset token string or None if user not found
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            return None
        
        # Generate secure token
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
        
        logger.info(f"Password reset token created for user {user.id}")
        
        # TODO: Send email with reset link
        # self._send_password_reset_email(user, token)
        
        return token
    
    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using token
        
        Args:
            token: Reset token
            new_password: New password
            
        Returns:
            True if successful, False otherwise
        """
        # Find valid token
        token_obj = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not token_obj:
            return False
        
        # Get user
        user = self.user_repo.get(token_obj.user_id)
        if not user:
            return False
        
        # ✅ Validate new password strength
        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_message)
        
        # Update password
        hashed_password = get_password_hash(new_password)
        self.user_repo.update(user.id, {'hashed_password': hashed_password})
        
        # Mark token as used
        token_obj.is_used = True
        token_obj.used_at = datetime.utcnow()
        
        # Revoke all refresh tokens for security
        self.revoke_user_tokens(user.id)
        
        self.commit()
        
        logger.info(f"Password reset successful for user {user.id}")
        
        return True
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
            
        Returns:
            True if successful, False if old password incorrect
        """
        user = self.user_repo.get(user_id)
        if not user:
            return False
        
        # Verify old password
        if not verify_password(old_password, user.hashed_password):
            return False
        
        # ✅ Validate new password strength
        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_message)
        
        # Update password
        hashed_password = get_password_hash(new_password)
        self.user_repo.update(user_id, {'hashed_password': hashed_password})
        
        # Revoke all refresh tokens for security
        self.revoke_user_tokens(user_id)
        
        self.commit()
        
        logger.info(f"Password changed for user {user_id}")
        
        return True
    
    def verify_email(self, token: str) -> bool:
        """
        Verify user email using verification token
        
        Args:
            token: Email verification token
            
        Returns:
            True if successful, False otherwise
        """
        from core.security import verify_email_verification_token
        
        user_id = verify_email_verification_token(token)
        if not user_id:
            return False
        
        user = self.user_repo.get(user_id)
        if not user:
            return False
        
        # Mark email as verified
        self.user_repo.update(user_id, {'is_verified': True})
        self.commit()
        
        logger.info(f"Email verified for user {user_id}")
        
        return True
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.user_repo.get_by_email(email)
    
    def check_account_lockout(self, email: str, ip_address: str) -> tuple[bool, Optional[str]]:
        """
        Check if account should be locked due to failed attempts
        
        Args:
            email: User email
            ip_address: Request IP address
            
        Returns:
            Tuple of (is_locked, reason)
        """
        # Check failed attempts in last 15 minutes
        fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
        
        failed_attempts = self.db.query(LoginAttempt).filter(
            LoginAttempt.email == email,
            LoginAttempt.success == False,
            LoginAttempt.attempted_at >= fifteen_minutes_ago
        ).count()
        
        if failed_attempts >= 5:
            return True, "Too many failed login attempts. Please try again later."
        
        return False, None
    
    def _log_login_attempt(
        self,
        email: str,
        success: bool,
        failure_reason: Optional[str] = None,
        ip_address: str = "0.0.0.0",
        user_agent: Optional[str] = None
    ):
        """
        Log login attempt for security monitoring
        
        Args:
            email: User email
            success: Whether login was successful
            failure_reason: Reason for failure if applicable
            ip_address: Request IP address
            user_agent: User agent string
        """
        login_attempt = LoginAttempt(
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            attempted_at=datetime.utcnow()
        )
        
        self.db.add(login_attempt)
        self.db.flush()
        
        if not success:
            logger.warning(
                f"Failed login attempt for {email} from {ip_address}. "
                f"Reason: {failure_reason}"
            )