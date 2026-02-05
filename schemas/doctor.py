"""
Alternative Solution: Proper TYPE_CHECKING usage in individual schema files

This demonstrates how to fix the Doctor schema file to properly handle
forward references. Apply this pattern to ALL schema files.
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict

# CRITICAL: Import actual types for runtime
from .user import UserInDB

# For type checking only (prevents circular imports)
if TYPE_CHECKING:
    from .department import Department
    from .user import User

# ============================================================================
# BASE MODELS
# ============================================================================

class DoctorBase(BaseModel):
    """Base Doctor schema with common fields"""
    specialization: str = Field(..., min_length=1, max_length=200)
    qualification: Optional[str] = Field(None, max_length=500)
    license_number: Optional[str] = Field(None, max_length=100)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    consultation_fee: int = Field(default=0, ge=0)
    average_consultation_time: int = Field(default=30, ge=5, le=240)
    bio: Optional[str] = None


class DoctorCreate(DoctorBase):
    """Schema for creating a new doctor"""
    user_id: int
    department_id: Optional[int] = None
    availability_schedule: Dict[str, Any] = Field(default_factory=dict)
    joined_date: Optional[date] = None


class DoctorUpdate(BaseModel):
    """Schema for updating doctor"""
    specialization: Optional[str] = Field(None, min_length=1, max_length=200)
    qualification: Optional[str] = Field(None, max_length=500)
    license_number: Optional[str] = Field(None, max_length=100)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    department_id: Optional[int] = None
    consultation_fee: Optional[int] = Field(None, ge=0)
    average_consultation_time: Optional[int] = Field(None, ge=5, le=240)
    availability_schedule: Optional[Dict[str, Any]] = None
    bio: Optional[str] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None


class DoctorAvailability(BaseModel):
    """Schema for updating doctor availability"""
    availability_schedule: Dict[str, Any]
    is_available: bool = True


# ============================================================================
# DATABASE MODELS (No forward references here)
# ============================================================================

class DoctorInDB(DoctorBase):
    """Doctor as stored in database (no relationships)"""
    id: int
    tenant_id: int
    user_id: int
    department_id: Optional[int] = None
    doctor_code: str
    availability_schedule: Dict[str, Any] = Field(default_factory=dict)
    is_available: bool = True
    is_active: bool = True
    joined_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RESPONSE MODELS (Use string annotations for forward refs)
# ============================================================================

class Doctor(DoctorInDB):
    """
    Doctor with relationships - uses string annotations for forward refs
    
    CRITICAL: We use string annotations like 'User' and 'Department'
    instead of importing the actual classes. This prevents circular imports.
    Pydantic will resolve these when model_rebuild() is called.
    """
    # String annotations - resolved at rebuild time
    user: Optional['User'] = None  # From schemas.user
    department: Optional['Department'] = None  # From schemas.department


class DoctorWithSchedule(Doctor):
    """Doctor with parsed schedule information"""
    upcoming_slots: Optional[Dict[str, Any]] = None
    total_appointments: int = 0


class DoctorStats(BaseModel):
    """Doctor statistics"""
    doctor_id: int
    doctor_name: str
    total_appointments: int = 0
    completed_appointments: int = 0
    cancelled_appointments: int = 0
    total_patients: int = 0
    average_rating: Optional[float] = None
    total_revenue: int = 0  # In cents/paise
    consultation_fee: int = 0


# ============================================================================
# IMPORTANT: Model rebuilding happens in __init__.py AFTER all imports
# ============================================================================