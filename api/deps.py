from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from core.database import SessionLocal
from core.config import settings
from core.security import decode_access_token
from models.user import User, UserRole
from models.tenant import Tenant
from repositories.user import UserRepository
from repositories.tenant import TenantRepository

security = HTTPBearer()

def get_db() -> Generator:
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    
    try:
        payload = decode_access_token(token)
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user_repo = UserRepository(db)
    user = user_repo.get(user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user

def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    """Get current user's tenant"""
    if current_user.role == UserRole.SUPER_ADMIN:
        # Super admin can access any tenant via header
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify tenant"
        )
    
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no associated tenant"
        )
    
    tenant_repo = TenantRepository(db)
    tenant = tenant_repo.get(current_user.tenant_id)
    
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive"
        )
    
    return tenant

def require_role(allowed_roles: list[UserRole]):
    """Dependency to check user role"""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require super admin role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user

def require_clinic_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require clinic admin or super admin role"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def check_subscription_feature(feature: str):
    """Check if tenant has access to feature"""
    def feature_checker(
        current_tenant: Tenant = Depends(get_current_tenant)
    ) -> Tenant:
        enabled_features = current_tenant.enabled_features or {}
        if not enabled_features.get(feature, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' not available in your subscription plan"
            )
        return current_tenant
    return feature_checker

def get_pagination_params(
    page: int = 1,
    page_size: int = 20
):
    """Pagination parameters"""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1"
        )
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be between 1 and 100"
        )
    
    skip = (page - 1) * page_size
    return {"skip": skip, "limit": page_size, "page": page, "page_size": page_size}