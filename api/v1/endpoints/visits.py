from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any

from api import deps
from schemas.visit import (
    Visit, VisitCreate, VisitUpdate
    # ❌ REMOVED: VisitWithDetails - moved to runtime import
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.visit_service import VisitService
from models.user import User, UserRole
from models.tenant import Tenant

router = APIRouter()    

@router.post("", response_model=Visit, status_code=status.HTTP_201_CREATED)
async def create_visit(
    visit_in: VisitCreate,
    current_user: User = Depends(deps.require_any_role([UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new visit/consultation record
    
    **Required Permissions:** Doctor, Clinic Admin, or Super Admin
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    
    try:
        visit = service.create_visit(visit_in)
        return visit
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Visit])
async def list_visits(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None
):
    """
    Get list of visits with filtering
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    
    # If user is a doctor, only show their visits
    filters = {}
    if current_user.role == UserRole.DOCTOR and current_user.doctor_profile:
        filters["doctor_id"] = current_user.doctor_profile.id
    elif doctor_id:
        filters["doctor_id"] = doctor_id
    
    if patient_id:
        filters["patient_id"] = patient_id
    
    result = service.get_visits(
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

# ✅ FIXED: Lazy response model for VisitWithDetails
@router.get("/{visit_id}", response_model=None)
async def get_visit(
    visit_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get visit with full details including billing
    
    **Returns:** VisitWithDetails (validated at runtime)
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    visit = service.get_visit_with_details(visit_id)
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    # Import and validate at runtime
    from schemas.visit import VisitWithDetails
    return VisitWithDetails.model_validate(visit)

@router.put("/{visit_id}", response_model=Visit)
async def update_visit(
    visit_id: int,
    visit_in: VisitUpdate,
    current_user: User = Depends(deps.require_any_role([UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update visit record
    
    **Required Permissions:** Doctor, Clinic Admin, or Super Admin
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    
    visit = service.update_visit(visit_id, visit_in)
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    return visit

@router.get("/patient/{patient_id}/history", response_model=List[Visit])
async def get_patient_visit_history(
    patient_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    limit: int = 10
):
    """
    Get patient's visit history
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    visits = service.get_patient_visit_history(patient_id, limit=limit)
    return visits

@router.post("/{visit_id}/complete", response_model=Visit)
async def complete_visit(
    visit_id: int,
    current_user: User = Depends(deps.require_any_role([UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Mark visit as completed
    """
    service = VisitService(db, current_tenant.id, current_user.id)
    
    visit = service.complete_visit(visit_id)
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    
    return visit