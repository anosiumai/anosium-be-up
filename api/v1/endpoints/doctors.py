from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import date

from api import deps
from schemas.doctor import (
    Doctor, DoctorCreate, DoctorUpdate,  # Keep simple schemas
    DoctorAvailability, DoctorStats
    # ❌ REMOVED: DoctorWithSchedule - moved to runtime import
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.doctor_service import DoctorService
from models.user import User, UserRole
from models.tenant import Tenant

router = APIRouter()

@router.post("", response_model=Doctor, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    doctor_in: DoctorCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new doctor profile
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Note:** User account must exist before creating doctor profile
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    try:
        doctor = service.create_doctor(doctor_in)
        return doctor
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Doctor])
async def list_doctors(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    department_id: Optional[int] = None,
    specialization: Optional[str] = None,
    is_available: Optional[bool] = None,
    is_active: bool = True
):
    """
    Get list of doctors with filtering
    
    **Filters:**
    - department_id: Filter by department
    - specialization: Filter by specialization
    - is_available: Filter by availability status
    - is_active: Filter active/inactive doctors
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    filters = {"is_active": is_active}
    if department_id:
        filters["department_id"] = department_id
    if specialization:
        filters["specialization"] = specialization
    if is_available is not None:
        filters["is_available"] = is_available
    
    result = service.get_doctors(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters=filters
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/{doctor_id}", response_model=Doctor)
async def get_doctor(
    doctor_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get doctor profile
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    doctor = service.get_doctor(doctor_id)
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return doctor

# ✅ FIXED: Lazy response model for DoctorWithSchedule
@router.get("/{doctor_id}/schedule", response_model=None)
async def get_doctor_schedule(
    doctor_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get doctor with weekly schedule
    
    **Returns:** DoctorWithSchedule (validated at runtime)
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    doctor_schedule = service.get_doctor_with_schedule(doctor_id)
    
    if not doctor_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Import and validate at runtime
    from schemas.doctor import DoctorWithSchedule
    return DoctorWithSchedule.model_validate(doctor_schedule)

@router.put("/{doctor_id}", response_model=Doctor)
async def update_doctor(
    doctor_id: int,
    doctor_in: DoctorUpdate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update doctor profile
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    doctor = service.update_doctor(doctor_id, doctor_in)
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return doctor

@router.put("/{doctor_id}/availability", response_model=Doctor)
async def update_doctor_availability(
    doctor_id: int,
    availability: List[DoctorAvailability],
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update doctor's weekly availability schedule
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    try:
        doctor = service.update_availability(doctor_id, availability)
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        
        return doctor
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{doctor_id}", response_model=SuccessResponse)
async def delete_doctor(
    doctor_id: int,
    soft_delete: bool = True,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete doctor profile (soft delete by default)
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    success = service.delete_doctor(doctor_id, soft=soft_delete)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Doctor deleted successfully"
    )

@router.get("/{doctor_id}/stats", response_model=DoctorStats)
async def get_doctor_stats(
    doctor_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Get doctor statistics and performance metrics
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    stats = service.get_doctor_stats(
        doctor_id,
        from_date=from_date,
        to_date=to_date
    )
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return stats

@router.post("/{doctor_id}/toggle-availability", response_model=Doctor)
async def toggle_doctor_availability(
    doctor_id: int,
    current_user: User = Depends(deps.require_any_role([UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Toggle doctor's availability status (available/unavailable)
    
    **Required Permissions:** Doctor (own profile), Clinic Admin, or Super Admin
    """
    service = DoctorService(db, current_tenant.id, current_user.id)
    
    # Check if user is trying to update their own profile
    if current_user.role == UserRole.DOCTOR:
        if not current_user.doctor_profile or current_user.doctor_profile.id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only toggle own availability"
            )
    
    doctor = service.toggle_availability(doctor_id)
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    return doctor