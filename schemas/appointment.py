from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_date: datetime
    duration_minutes: int = Field(ge=15, le=240, default=30)
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    appointment_date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(ge=15, le=240, default=None)
    status: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    clinic_id: int
    patient_id: int
    doctor_id: int
    appointment_number: str
    appointment_date: datetime
    duration_minutes: int
    status: str
    reason: Optional[str]
    notes: Optional[str]
    booked_via_ai: bool
    reminder_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True