"""
API Dependencies
Common dependencies for route handlers including authentication, authorization, and utilities
"""

from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from core.database import get_db
from core.security import decode_token
from models.user import User, UserRole
from models.tenant import Tenant
from repositories.user import UserRepository
from repositories.tenant import TenantRepository

# Security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user ID
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_repo = UserRepository(db)
    user = user_repo.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-ID")
) -> Tenant:
    """
    Get current tenant from user or header
    
    Super admins can specify tenant via X-Tenant-ID header.
    Other users use their own tenant.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        x_tenant_id: Optional tenant ID from header (super admin only)
        
    Returns:
        Current tenant
        
    Raises:
        HTTPException: If tenant not found or user doesn't have access
    """
    # Super admins can override tenant via header
    if current_user.role == UserRole.SUPER_ADMIN and x_tenant_id:
        tenant_id = x_tenant_id
    else:
        tenant_id = current_user.tenant_id
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant specified"
        )
    
    # Get tenant
    tenant_repo = TenantRepository(db)
    tenant = tenant_repo.get(tenant_id)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive"
        )
    
    return tenant


def require_role(required_role: UserRole):
    """
    Dependency factory for role-based access control
    
    Args:
        required_role: Minimum required role
        
    Returns:
        Dependency function
        
    Example:
        @router.get("/admin-only")
        def admin_endpoint(
            user: User = Depends(require_role(UserRole.CLINIC_ADMIN))
        ):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # Define role hierarchy
        role_hierarchy = {
            UserRole.SUPER_ADMIN: 5,
            UserRole.CLINIC_ADMIN: 4,
            UserRole.DOCTOR: 3,
            UserRole.ACCOUNTANT: 2,
            UserRole.RECEPTIONIST: 2,
            UserRole.STAFF: 1,
        }
        
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. {required_role.value} role required."
            )
        
        return current_user
    
    return role_checker


def require_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require super admin role
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if super admin
        
    Raises:
        HTTPException: If user is not super admin
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


def require_clinic_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require clinic admin or super admin role
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def check_subscription_feature(feature: str):
    """
    Dependency factory to check if tenant has access to a feature
    
    Args:
        feature: Feature name to check
        
    Returns:
        Dependency function
        
    Example:
        @router.post("/ai-feature")
        def ai_endpoint(
            tenant: Tenant = Depends(check_subscription_feature("ai_chatbot"))
        ):
            ...
    """
    def feature_checker(
        current_tenant: Tenant = Depends(get_current_tenant)
    ) -> Tenant:
        enabled_features = current_tenant.enabled_features or {}
        
        if not enabled_features.get(feature, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' is not enabled for your subscription tier"
            )
        
        return current_tenant
    
    return feature_checker


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
) -> dict:
    """
    Get pagination parameters
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        
    Returns:
        Dictionary with skip, limit, page, page_size
    """
    skip = (page - 1) * page_size
    return {
        "skip": skip,
        "limit": page_size,
        "page": page,
        "page_size": page_size
    }


def get_current_user_id(
    current_user: User = Depends(get_current_user)
) -> int:
    """
    Get current user ID
    
    Convenience dependency for endpoints that only need the user ID
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User ID
    """
    return current_user.id


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    
    Use for endpoints that are public but may have different behavior for authenticated users
    
    Args:
        credentials: Optional bearer token
        db: Database session
        
    Returns:
        User or None
    """
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None