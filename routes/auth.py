"""
Authentication Routes
Handles login, user creation, and authentication operations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from schemas.auth import UserLogin, TokenResponse
from schemas.user import UserCreate, UserResponse, UserUpdate
from schemas.clinic import ClinicResponse
from schemas.common import MessageResponse
from core.security import (
    AuthService, get_current_user, require_role,
    check_clinic_access
)
from services.multi_clinic import MultiClinicService
from models.user import User
from models.base import UserRole
from models.clinic import Clinic

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    """
    user = AuthService.authenticate_user(db, credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check subscription
    if not MultiClinicService.is_subscription_active(user.clinic):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic subscription is not active. Please contact support."
        )
    
    # Create access token
    access_token = AuthService.create_access_token(
        data={
            "user_id": user.id,
            "username": user.username,
            "clinic_id": user.clinic_id,
            "role": user.role.value
        }
    )
    
    # Prepare response
    user_response = UserResponse(
        id=user.id,
        clinic_id=user.clinic_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        specialization=user.specialization,
        license_number=user.license_number,
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at
    )
    
    clinic_response = ClinicResponse(
        id=user.clinic.id,
        clinic_code=user.clinic.clinic_code,
        name=user.clinic.name,
        email=user.clinic.email,
        phone=user.clinic.phone,
        address=user.clinic.address,
        logo_url=user.clinic.logo_url,
        primary_color=user.clinic.primary_color,
        secondary_color=user.clinic.secondary_color,
        subscription_tier=user.clinic.subscription_tier.value,
        subscription_status=user.clinic.subscription_status.value,
        features=user.clinic.features,
        ai_config=user.clinic.ai_config,
        is_active=user.clinic.is_active,
        created_at=user.clinic.created_at
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        clinic=clinic_response
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """
    Register a new user
    Only admins can create users
    """
    # Clinic admins can only create users in their clinic
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != user_data.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create users in other clinics"
        )
    
    # Check if clinic exists
    clinic = MultiClinicService.get_clinic_by_id(db, user_data.clinic_id)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    # Check doctor limit for doctor role
    if user_data.role == UserRole.DOCTOR:
        limit_check = MultiClinicService.check_limit(db, clinic, "doctors")
        if not limit_check["can_add"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Doctor limit reached ({limit_check['current']}/{limit_check['limit']}). Upgrade subscription."
            )
    
    try:
        user = AuthService.create_user(
            db=db,
            clinic_id=user_data.clinic_id,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role,
            phone=user_data.phone,
            specialization=user_data.specialization,
            license_number=user_data.license_number
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's information"""
    update_data = user_update.dict(exclude_unset=True)
    
    # Users cannot change their own active status
    if "is_active" in update_data:
        del update_data["is_active"]
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/{clinic_id}/users", response_model=List[UserResponse])
async def list_clinic_users(
    clinic_id: int,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List users in a clinic"""
    # Check access
    if not check_clinic_access(current_user, clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    from sqlalchemy import and_
    query = db.query(User).filter(User.clinic_id == clinic_id)
    
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    users = query.offset(skip).limit(limit).all()
    return users


@router.get("/{clinic_id}/users/{user_id}", response_model=UserResponse)
async def get_user(
    clinic_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID"""
    if not check_clinic_access(current_user, clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.clinic_id == clinic_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{clinic_id}/users/{user_id}", response_model=UserResponse)
async def update_user(
    clinic_id: int,
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """Update user information (Admin only)"""
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.clinic_id == clinic_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{clinic_id}/users/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    clinic_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """Deactivate user (Admin only)"""
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    # Cannot deactivate yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.clinic_id == clinic_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    db.commit()
    
    return MessageResponse(message="User deactivated successfully")


@router.post("/{clinic_id}/users/{user_id}/activate", response_model=MessageResponse)
async def activate_user(
    clinic_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """Activate user (Admin only)"""
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.clinic_id == clinic_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    db.commit()
    
    return MessageResponse(message="User activated successfully")