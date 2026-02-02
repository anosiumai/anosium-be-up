from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.patient import (
    Patient, PatientCreate, PatientUpdate, PatientWithHistory,
    PatientSearch, PatientStats
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.patient_service import PatientService
from models.user import User, UserRole
from models.tenant import Tenant

router = APIRouter()

@router.post("", response_model=Patient, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_in: PatientCreate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new patient
    
    **Required Permissions:** Any authenticated user
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    patient = service.create_patient(patient_in)
    return patient

@router.get("", response_model=PaginatedResponse[Patient])
async def list_patients(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    search: Optional[str] = Query(None, min_length=2),
    gender: Optional[str] = None,
    is_active: bool = True
):
    """
    Get list of patients with pagination and filtering
    
    **Filters:**
    - search: Search by name, phone, or patient code
    - gender: Filter by gender
    - is_active: Filter active/inactive patients
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    
    filters = {"is_active": is_active}
    if gender:
        filters["gender"] = gender
    
    result = service.get_patients(
        skip=pagination["skip"],
        limit=pagination["limit"],
        search=search,
        filters=filters
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get patient by ID
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    patient = service.get_patient(patient_id)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient

@router.get("/{patient_id}/history", response_model=PatientWithHistory)
async def get_patient_history(
    patient_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get patient with complete medical history
    
    **Includes:**
    - Recent visits
    - Upcoming appointments
    - Statistics
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    patient_history = service.get_patient_with_history(patient_id)
    
    if not patient_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient_history

@router.put("/{patient_id}", response_model=Patient)
async def update_patient(
    patient_id: int,
    patient_in: PatientUpdate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update patient information
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    patient = service.update_patient(patient_id, patient_in)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient

@router.delete("/{patient_id}", response_model=SuccessResponse)
async def delete_patient(
    patient_id: int,
    soft_delete: bool = True,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete patient (soft delete by default)
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    success = service.delete_patient(patient_id, soft=soft_delete)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Patient deleted successfully"
    )

@router.get("/{patient_id}/stats", response_model=PatientStats)
async def get_patient_stats(
    patient_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get patient statistics
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    stats = service.get_patient_stats(patient_id)
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return stats

@router.post("/search", response_model=List[Patient])
async def search_patients(
    search_params: PatientSearch,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Advanced patient search
    """
    service = PatientService(db, current_tenant.id, current_user.id)
    patients = service.search_patients(search_params)
    return patients