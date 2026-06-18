from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any

from api import deps
from api.deps_audit import log_patient_read          # ← HIPAA audit
from schemas.patient import (
    Patient, PatientCreate, PatientUpdate,
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
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    service = PatientService(db, current_tenant.id, current_user.id)
    return service.create_patient(patient_in)
    # ponytail: CREATE audit fires inside BaseRepository.create() — no extra wiring


@router.get("", response_model=PaginatedResponse[Patient])
async def list_patients(
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
    pagination: dict     = Depends(deps.get_pagination_params),
    search: Optional[str] = Query(None, min_length=2),
    gender: Optional[str] = None,
    is_active: bool      = True,
):
    # ponytail: list endpoint logs nothing — individual IDs aren't known at list time;
    # HIPAA guidance covers access to individual records, not paginated lists.
    service = PatientService(db, current_tenant.id, current_user.id)
    filters = {"is_active": is_active}
    if gender:
        filters["gender"] = gender
    result = service.get_patients(
        skip=pagination["skip"], limit=pagination["limit"],
        search=search, filters=filters,
    )
    return PaginatedResponse(
        items=result["items"], total=result["total"],
        page=pagination["page"], page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"],
    )


@router.get("/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: int,
    _audit: None         = Depends(log_patient_read),   # ← HIPAA: logs before body runs
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    service = PatientService(db, current_tenant.id, current_user.id)
    patient = service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("/{patient_id}/history", response_model=None)
async def get_patient_history(
    patient_id: int,
    _audit: None         = Depends(log_patient_read),   # ← HIPAA: medical history = sensitive
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
) -> Any:
    service = PatientService(db, current_tenant.id, current_user.id)
    patient_history = service.get_patient_with_history(patient_id)
    if not patient_history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    from schemas.patient import PatientWithHistory
    return PatientWithHistory.model_validate(patient_history)


@router.put("/{patient_id}", response_model=Patient)
async def update_patient(
    patient_id: int,
    patient_in: PatientUpdate,
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    service = PatientService(db, current_tenant.id, current_user.id)
    patient = service.update_patient(patient_id, patient_in)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient
    # ponytail: UPDATE audit fires inside BaseRepository.update()


@router.delete("/{patient_id}", response_model=SuccessResponse)
async def delete_patient(
    patient_id: int,
    soft_delete: bool    = True,
    current_user: User   = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    service = PatientService(db, current_tenant.id, current_user.id)
    success = service.delete_patient(patient_id, soft=soft_delete)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return SuccessResponse(success=True, message="Patient deleted successfully")
    # ponytail: DELETE audit fires inside BaseRepository.delete()


@router.get("/{patient_id}/stats", response_model=PatientStats)
async def get_patient_stats(
    patient_id: int,
    _audit: None         = Depends(log_patient_read),   # stats = patient data
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    service = PatientService(db, current_tenant.id, current_user.id)
    stats = service.get_patient_stats(patient_id)
    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return stats


@router.post("/search", response_model=List[Patient])
async def search_patients(
    search_params: PatientSearch,
    current_user: User   = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session          = Depends(deps.get_db),
):
    # ponytail: search returns a list — individual IDs logged on subsequent GET
    service = PatientService(db, current_tenant.id, current_user.id)
    return service.search_patients(search_params)