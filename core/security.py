"""
Security utilities for authentication and authorization
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt

from core.config import settings


# Password hashing context
pwd_context = CryptContext(
    schemes=["sha256_crypt"],
    deprecated="auto"
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength based on configured requirements
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
    
    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    if settings.PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
    
    return True, None


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time (defaults to settings value)
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time (defaults to settings value)
        
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify JWT token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_token_type(token_payload: Dict[str, Any], expected_type: str) -> bool:
    """
    Verify that token is of expected type (access or refresh)
    
    Args:
        token_payload: Decoded token payload
        expected_type: Expected token type ('access' or 'refresh')
        
    Returns:
        True if token type matches, False otherwise
    """
    return token_payload.get("type") == expected_type


def is_token_expired(token_payload: Dict[str, Any]) -> bool:
    """
    Check if token is expired
    
    Args:
        token_payload: Decoded token payload
        
    Returns:
        True if token is expired, False otherwise
    """
    exp = token_payload.get("exp")
    if not exp:
        return True
    
    return datetime.fromtimestamp(exp) < datetime.utcnow()


def extract_user_id_from_token(token: str) -> Optional[int]:
    """
    Extract user ID from token
    
    Args:
        token: JWT token
        
    Returns:
        User ID or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    return payload.get("user_id")


def extract_tenant_id_from_token(token: str) -> Optional[int]:
    """
    Extract tenant ID from token
    
    Args:
        token: JWT token
        
    Returns:
        Tenant ID or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    return payload.get("tenant_id")


def create_password_reset_token(user_id: int) -> str:
    """
    Create password reset token
    
    Args:
        user_id: User ID
        
    Returns:
        Encoded JWT token for password reset
    """
    expire = datetime.utcnow() + timedelta(hours=1)
    
    to_encode = {
        "user_id": user_id,
        "exp": expire,
        "type": "password_reset"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[int]:
    """
    Verify password reset token and extract user ID
    
    Args:
        token: Password reset token
        
    Returns:
        User ID or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    if payload.get("type") != "password_reset":
        return None
    
    if is_token_expired(payload):
        return None
    
    return payload.get("user_id")


def create_email_verification_token(user_id: int) -> str:
    """
    Create email verification token
    
    Args:
        user_id: User ID
        
    Returns:
        Encoded JWT token for email verification
    """
    expire = datetime.utcnow() + timedelta(days=7)
    
    to_encode = {
        "user_id": user_id,
        "exp": expire,
        "type": "email_verification"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_email_verification_token(token: str) -> Optional[int]:
    """
    Verify email verification token and extract user ID
    
    Args:
        token: Email verification token
        
    Returns:
        User ID or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    if payload.get("type") != "email_verification":
        return None
    
    if is_token_expired(payload):
        return None
    
    return payload.get("user_id")


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage
    
    Args:
        api_key: Plain API key
        
    Returns:
        Hashed API key
    """
    return get_password_hash(api_key)


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """
    Verify API key
    
    Args:
        plain_api_key: Plain API key
        hashed_api_key: Hashed API key from database
        
    Returns:
        True if API key is valid, False otherwise
    """
    return verify_password(plain_api_key, hashed_api_key)