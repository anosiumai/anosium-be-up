"""
FastAPI Routes for Multi-Clinic Management
Handles clinic CRUD, subscription, and tenant operations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from schemas.clinic import ClinicCreate, ClinicUpdate, ClinicResponse, ClinicStats
from schemas.common import MessageResponse
from models.base import SubscriptionTier
from services.multi_clinic import MultiClinicService
from core.security import get_current_user, require_role
from models.user import User
from models.base import UserRole
from models.clinic import Clinic

router = APIRouter(prefix="/api/clinics", tags=["Multi-Clinic"])


@router.post("/", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
async def create_clinic(
    clinic_data: ClinicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """
    Create a new clinic (Super Admin only)
    Automatically sets up trial subscription
    """
    # Check if email already exists
    existing = db.query(Clinic).filter(Clinic.email == clinic_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clinic with this email already exists"
        )
    
    clinic = MultiClinicService.create_clinic(db, clinic_data)
    return clinic


@router.get("/{clinic_id}", response_model=ClinicResponse)
async def get_clinic(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get clinic details"""
    # Users can only access their own clinic unless super admin
    if current_user.role != UserRole.SUPER_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return clinic


@router.get("/code/{clinic_code}", response_model=ClinicResponse)
async def get_clinic_by_code(
    clinic_code: str,
    db: Session = Depends(get_db)
):
    """Get clinic by code (public endpoint for login)"""
    clinic = MultiClinicService.get_clinic_by_code(db, clinic_code)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return clinic


@router.put("/{clinic_id}", response_model=ClinicResponse)
async def update_clinic(
    clinic_id: int,
    clinic_data: ClinicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """Update clinic details (Clinic Admin or Super Admin)"""
    # Clinic admins can only update their own clinic
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = MultiClinicService.update_clinic(db, clinic_id, clinic_data)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return clinic


@router.get("/{clinic_id}/stats", response_model=ClinicStats)
async def get_clinic_stats(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """Get clinic statistics"""
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    stats = MultiClinicService.get_clinic_stats(db, clinic_id)
    return stats


@router.post("/{clinic_id}/upgrade", response_model=ClinicResponse)
async def upgrade_subscription(
    clinic_id: int,
    new_tier: SubscriptionTier,
    duration_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """
    Upgrade clinic subscription
    Super Admin: Can upgrade any clinic
    Clinic Admin: Can upgrade own clinic
    """
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = MultiClinicService.upgrade_subscription(db, clinic_id, new_tier, duration_days)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return clinic


@router.get("/{clinic_id}/limits/{limit_type}")
async def check_clinic_limit(
    clinic_id: int,
    limit_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]))
):
    """
    Check if clinic has reached subscription limits
    limit_type: 'doctors' or 'patients'
    """
    if current_user.role == UserRole.CLINIC_ADMIN and current_user.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )
    
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    limit_info = MultiClinicService.check_limit(db, clinic, limit_type)
    return limit_info


@router.get("/", response_model=List[ClinicResponse])
async def list_clinics(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """List all clinics (Super Admin only)"""
    clinics = MultiClinicService.list_clinics(db, skip, limit, is_active)
    return clinics


@router.delete("/{clinic_id}", response_model=MessageResponse)
async def deactivate_clinic(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Deactivate clinic (Super Admin only)"""
    success = MultiClinicService.deactivate_clinic(db, clinic_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return MessageResponse(message="Clinic deactivated successfully")


@router.get("/expiring/subscriptions")
async def get_expiring_subscriptions(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Get clinics with subscriptions expiring soon (Super Admin only)"""
    clinics = MultiClinicService.get_expiring_subscriptions(db, days)
    return clinics