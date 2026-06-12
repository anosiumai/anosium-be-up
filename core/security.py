"""
Security utilities for authentication and authorization
FIXED: Using bcrypt directly instead of passlib for better compatibility
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import bcrypt
from jose import JWTError, jwt
from core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
        
    Note:
        bcrypt has a 72-byte limit. We truncate if needed.
    """
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

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