# schemas/appointment.py
from pydantic import BaseModel, Field, validator
from typing import Optional, TYPE_CHECKING
from datetime import date, time, datetime
from models.appointment import AppointmentStatus, AppointmentType

if TYPE_CHECKING:
    from schemas.patient import Patient
    from schemas.doctor import Doctor
    from schemas.visit import Visit
    from schemas.ai_lead import AILead


class AppointmentBase(BaseModel):
    appointment_date: date
    appointment_time: time
    duration_minutes: int = Field(default=30, ge=10, le=240)
    appointment_type: AppointmentType = AppointmentType.NEW_CONSULTATION
    reason: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

    @validator("appointment_date")
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError("Appointment date cannot be in the past")
        return v


class AppointmentCreate(AppointmentBase):
    patient_id: int
    doctor_id: int
    booked_via_ai: bool = False
    ai_lead_id: Optional[int] = None


class AppointmentUpdate(BaseModel):
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, ge=10, le=240)
    reason: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[AppointmentStatus] = None


class AppointmentReschedule(BaseModel):
    new_date: date
    new_time: time
    reason: str = Field(..., min_length=5)

    @validator("new_date")
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError("New date cannot be in the past")
        return v


class AppointmentCancel(BaseModel):
    cancellation_reason: str = Field(..., min_length=5, max_length=500)


class AppointmentInDB(AppointmentBase):
    id: int
    tenant_id: int
    patient_id: int
    doctor_id: int
    appointment_code: str
    status: AppointmentStatus
    booked_via_ai: bool
    ai_lead_id: Optional[int]
    reminder_sent: bool
    reminder_sent_at: Optional[datetime]
    checked_in_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    created_at: Optional[datetime] = None  # was: created_at: datetime
    updated_at: Optional[datetime] = None  # was: updated_at: datetime
    created_by: Optional[int]


class Appointment(AppointmentInDB):
    patient: "Patient"
    doctor: "Doctor"


class AppointmentWithDetails(Appointment):
    visit: Optional["Visit"] = None
    ai_lead: Optional["AILead"] = None


class DoctorAvailabilitySlot(BaseModel):
    date: date
    time: time
    duration_minutes: int
    is_available: bool
    doctor_id: int
    doctor_name: str
