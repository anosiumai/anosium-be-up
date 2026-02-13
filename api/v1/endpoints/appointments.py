# api/v1/endpoints/appointments.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import date, time, datetime

from api import deps
from schemas.appointment import (
    Appointment, AppointmentCreate, AppointmentUpdate,
    # ❌ REMOVED: AppointmentWithDetails - moved to runtime import
    AppointmentReschedule, AppointmentCancel,
    DoctorAvailabilitySlot
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.appointment_service import AppointmentService
from models.user import User
from models.tenant import Tenant
from models.appointment import AppointmentStatus

router = APIRouter()

@router.post("", response_model=Appointment, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appointment_in: AppointmentCreate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new appointment
    
    **Validations:**
    - Doctor availability check
    - No overlapping appointments
    - Patient and doctor belong to same tenant
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    try:
        appointment = service.create_appointment(appointment_in)
        return appointment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Appointment])
async def list_appointments(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Get list of appointments with filtering
    
    **Filters:**
    - patient_id: Filter by patient
    - doctor_id: Filter by doctor
    - status: Filter by status
    - from_date/to_date: Date range filter
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if patient_id:
        filters["patient_id"] = patient_id
    if doctor_id:
        filters["doctor_id"] = doctor_id
    if status:
        filters["status"] = status
    
    result = service.get_appointments(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters=filters,
        from_date=from_date,
        to_date=to_date
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/today", response_model=List[Appointment])
async def get_today_appointments(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    doctor_id: Optional[int] = None
):
    """
    Get today's appointments
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    appointments = service.get_today_appointments(doctor_id=doctor_id)
    return appointments

@router.get("/upcoming", response_model=List[Appointment])
async def get_upcoming_appointments(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    days: int = Query(7, ge=1, le=30),
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None
):
    """
    Get upcoming appointments (next N days)
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    appointments = service.get_upcoming_appointments(
        days=days,
        patient_id=patient_id,
        doctor_id=doctor_id
    )
    return appointments

# ✅ FIXED: Lazy response model for AppointmentWithDetails
@router.get("/{appointment_id}", response_model=None)
async def get_appointment(
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get appointment with full details
    
    **Returns:** AppointmentWithDetails (validated at runtime)
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    appointment = service.get_appointment_with_details(appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Import and validate at runtime
    from schemas.appointment import AppointmentWithDetails
    return AppointmentWithDetails.model_validate(appointment)

@router.put("/{appointment_id}", response_model=Appointment)
async def update_appointment(
    appointment_id: int,
    appointment_in: AppointmentUpdate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update appointment
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    try:
        appointment = service.update_appointment(appointment_id, appointment_in)
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return appointment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{appointment_id}/reschedule", response_model=Appointment)
async def reschedule_appointment(
    appointment_id: int,
    reschedule_data: AppointmentReschedule,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Reschedule appointment to new date/time
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    try:
        appointment = service.reschedule_appointment(appointment_id, reschedule_data)
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return appointment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{appointment_id}/cancel", response_model=SuccessResponse)
async def cancel_appointment(
    appointment_id: int,
    cancel_data: AppointmentCancel,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Cancel appointment
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    success = service.cancel_appointment(appointment_id, cancel_data.cancellation_reason)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Appointment cancelled successfully"
    )

@router.post("/{appointment_id}/check-in", response_model=Appointment)
async def check_in_appointment(
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Check in patient for appointment
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    appointment = service.check_in_appointment(appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    return appointment

@router.post("/{appointment_id}/complete", response_model=Appointment)
async def complete_appointment(
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Mark appointment as completed
    """
    service = AppointmentService(db, current_tenant.id, current_user.id)
    
    appointment = service.complete_appointment(appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    return appointment

@router.get("/doctor/{doctor_id}/availability", response_model=List[DoctorAvailabilitySlot])
async def get_doctor_availability(
    doctor_id: int,
    from_date: date = Query(...),
    to_date: date = Query(...),
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get doctor's available time slots for booking
    
    **Parameters:**
    - from_date: Start date
    - to_date: End date (max 30 days from start)
    """
    if (to_date - from_date).days > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 30 days"
        )
    
    service = AppointmentService(db, current_tenant.id, current_user.id)
    slots = service.get_doctor_availability(doctor_id, from_date, to_date)
    
    return slots