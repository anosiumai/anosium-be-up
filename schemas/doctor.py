from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import date, datetime, time

if TYPE_CHECKING:
    from schemas.user import User
    from schemas.department import Department

class DoctorBase(BaseModel):
    """Base doctor schema"""
    specialization: str = Field(..., min_length=2, max_length=200)
    qualification: Optional[str] = Field(None, max_length=500)
    license_number: Optional[str] = Field(None, max_length=100)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    consultation_fee: int = Field(default=0, ge=0)
    average_consultation_time: int = Field(default=30, ge=10, le=240)
    bio: Optional[str] = None
    
    class Config:
        from_attributes = True

class DoctorCreate(DoctorBase):
    """Create doctor schema"""
    user_id: int
    department_id: Optional[int] = None
    availability_schedule: Optional[Dict[str, Any]] = None
    joined_date: Optional[date] = None

class DoctorUpdate(BaseModel):
    """Update doctor schema"""
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    license_number: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    consultation_fee: Optional[int] = Field(None, ge=0)
    average_consultation_time: Optional[int] = Field(None, ge=10, le=240)
    department_id: Optional[int] = None
    availability_schedule: Optional[Dict[str, Any]] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None
    bio: Optional[str] = None

class DoctorAvailability(BaseModel):
    """Doctor availability for a day"""
    day: str = Field(..., pattern=r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$')
    is_available: bool = True
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slots: Optional[int] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None

class DoctorInDB(DoctorBase):
    """Doctor from database"""
    id: int
    tenant_id: int
    user_id: int
    department_id: Optional[int]
    doctor_code: str
    availability_schedule: Dict[str, Any]
    is_available: bool
    is_active: bool
    joined_date: Optional[date]
    created_at: datetime
    updated_at: Optional[datetime]

class Doctor(DoctorInDB):
    """Public doctor schema"""
    user: 'User'  # Forward reference
    department: Optional['Department'] = None

class DoctorWithSchedule(Doctor):
    """Doctor with weekly schedule"""
    weekly_schedule: List[DoctorAvailability]

class DoctorStats(BaseModel):
    """Doctor statistics"""
    total_appointments: int = 0
    completed_appointments: int = 0
    cancelled_appointments: int = 0
    average_rating: Optional[float] = None
    total_patients: int = 0
    today_appointments: int = 0