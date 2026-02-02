from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from models.patient import Gender, BloodGroup

if TYPE_CHECKING:
    from schemas.visit import Visit
    from schemas.appointment import Appointment

class PatientBase(BaseModel):
    """Base patient schema"""
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: date
    gender: Gender
    email: Optional[EmailStr] = None
    phone: str = Field(..., regex=r'^\+?[1-9]\d{1,14}$')
    alternate_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @validator('date_of_birth')
    def validate_dob(cls, v):
        if v >= date.today():
            raise ValueError('Date of birth must be in the past')
        age = (date.today() - v).days // 365
        if age > 150:
            raise ValueError('Invalid date of birth')
        return v

class PatientCreate(PatientBase):
    """Create patient schema"""
    blood_group: Optional[BloodGroup] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = None
    referred_by: Optional[str] = None
    notes: Optional[str] = None

class PatientUpdate(BaseModel):
    """Update patient schema"""
    first_name: Optional[str] = Field(None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class PatientInDB(PatientBase):
    """Patient from database"""
    id: int
    tenant_id: int
    patient_code: str
    blood_group: Optional[BloodGroup]
    allergies: Optional[str]
    chronic_conditions: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    registration_date: date
    referred_by: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

class Patient(PatientInDB):
    """Public patient schema"""
    full_name: str
    age: int
    
    @validator('full_name', pre=True, always=True)
    def set_full_name(cls, v, values):
        return f"{values.get('first_name', '')} {values.get('last_name', '')}".strip()
    
    @validator('age', pre=True, always=True)
    def calculate_age(cls, v, values):
        dob = values.get('date_of_birth')
        if dob:
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return 0

class PatientSearch(BaseModel):
    """Patient search parameters"""
    query: Optional[str] = Field(None, min_length=2)
    gender: Optional[Gender] = None
    min_age: Optional[int] = Field(None, ge=0, le=150)
    max_age: Optional[int] = Field(None, ge=0, le=150)
    city: Optional[str] = None
    is_active: bool = True

class PatientStats(BaseModel):
    """Patient statistics"""
    total_visits: int = 0
    last_visit_date: Optional[datetime] = None
    total_spent: int = 0
    pending_balance: int = 0
    upcoming_appointments: int = 0

class PatientWithHistory(Patient):
    """Patient with medical history"""
    stats: PatientStats
    recent_visits: List['Visit'] = []
    recent_appointments: List['Appointment'] = []