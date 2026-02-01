"""
Authentication & Authorization Module
Handles JWT tokens, password hashing, and role-based access
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import os

from core.database import get_db
from models.user import User
from models.base import UserRole
from schemas.auth import TokenResponse
from schemas.user import UserResponse
from schemas.clinic import ClinicResponse

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token
security = HTTPBearer()


class AuthService:
    """Authentication service for password and token management"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            return None
        
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user
    
    @staticmethod
    def create_user(
        db: Session,
        clinic_id: int,
        username: str,
        email: str,
        password: str,
        full_name: str,
        role: UserRole,
        phone: Optional[str] = None,
        specialization: Optional[str] = None,
        license_number: Optional[str] = None
    ) -> User:
        """Create a new user"""
        # Check if username or email exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            raise ValueError("Username or email already exists")
        
        hashed_password = AuthService.hash_password(password)
        
        user = User(
            clinic_id=clinic_id,
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            phone=phone,
            role=role,
            specialization=specialization,
            license_number=license_number
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user


# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user
    Validates JWT token and returns user object
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = AuthService.decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Check subscription status
    from services.multi_clinic import MultiClinicService
    if not MultiClinicService.is_subscription_active(user.clinic):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic subscription is not active"
        )
    
    return user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory to require specific roles
    Usage: current_user = Depends(require_role([UserRole.ADMIN, UserRole.DOCTOR]))
    """
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_checker


async def require_clinic_access(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure user has access to clinic resources
    Super admins have access to all clinics
    """
    return current_user


# Optional authentication (for public endpoints that can benefit from user context)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Optional authentication - returns None if not authenticated"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def check_clinic_access(user: User, clinic_id: int) -> bool:
    """
    Check if user has access to specific clinic
    Super admins have access to all clinics
    Other users only have access to their own clinic
    """
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    return user.clinic_id == clinic_id


def check_permission(user: User, permission: str) -> bool:
    """
    Check if user has specific permission based on role
    Permissions hierarchy:
    - SUPER_ADMIN: All permissions
    - CLINIC_ADMIN: Clinic management, all clinic operations
    - DOCTOR: Patient records, appointments, prescriptions
    - RECEPTIONIST: Appointments, basic patient info
    - STAFF: View-only access
    """
    role_permissions = {
        UserRole.SUPER_ADMIN: ["*"],  # All permissions
        UserRole.CLINIC_ADMIN: [
            "manage_clinic", "manage_users", "manage_patients",
            "manage_appointments", "manage_billing", "view_analytics",
            "manage_ai", "manage_leads"
        ],
        UserRole.DOCTOR: [
            "view_patients", "edit_patients", "view_appointments",
            "edit_appointments", "view_medical_records", "edit_medical_records"
        ],
        UserRole.RECEPTIONIST: [
            "view_patients", "edit_patients", "view_appointments",
            "create_appointments", "edit_appointments", "view_billing"
        ],
        UserRole.STAFF: [
            "view_patients", "view_appointments"
        ]
    }
    
    user_permissions = role_permissions.get(user.role, [])
    
    # Super admin has all permissions
    if "*" in user_permissions:
        return True
    
    return permission in user_permissions