from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import date, datetime
from models.visit import VisitStatus

if TYPE_CHECKING:
    from schemas.patient import Patient
    from schemas.doctor import Doctor
    from schemas.billing import VisitService, Invoice

class Vitals(BaseModel):
    """Patient vitals"""
    blood_pressure: Optional[str] = Field(None, pattern=r'^\d{2,3}/\d{2,3}$')
    temperature: Optional[float] = Field(None, ge=90, le=110)
    pulse: Optional[int] = Field(None, ge=30, le=200)
    respiratory_rate: Optional[int] = Field(None, ge=8, le=40)
    oxygen_saturation: Optional[int] = Field(None, ge=70, le=100)
    weight: Optional[float] = Field(None, ge=0, le=500)
    height: Optional[float] = Field(None, ge=0, le=300)
    bmi: Optional[float] = None
    
    @validator('bmi', always=True)
    def calculate_bmi(cls, v, values):
        weight = values.get('weight')
        height = values.get('height')
        if weight and height and height > 0:
            height_m = height / 100
            return round(weight / (height_m ** 2), 2)
        return v

class Prescription(BaseModel):
    """Medication prescription"""
    medicine: str = Field(..., min_length=2)
    dosage: str = Field(..., min_length=1)
    frequency: str = Field(..., min_length=2)
    duration: str = Field(..., min_length=1)
    instructions: Optional[str] = None

class LabTest(BaseModel):
    """Lab test order"""
    test_name: str = Field(..., min_length=2)
    test_code: Optional[str] = None
    instructions: Optional[str] = None
    urgent: bool = False

class VisitBase(BaseModel):
    """Base visit schema"""
    chief_complaint: str = Field(..., min_length=5)
    symptoms: List[str] = []
    vitals: Optional[Vitals] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    
    class Config:
        from_attributes = True

class VisitCreate(VisitBase):
    """Create visit schema"""
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int] = None
    prescriptions: List[Prescription] = []
    lab_tests_ordered: List[LabTest] = []
    procedures_performed: List[str] = []
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None
    follow_up_notes: Optional[str] = None

class VisitUpdate(BaseModel):
    """Update visit schema"""
    chief_complaint: Optional[str] = None
    symptoms: Optional[List[str]] = None
    vitals: Optional[Vitals] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    prescriptions: Optional[List[Prescription]] = None
    lab_tests_ordered: Optional[List[LabTest]] = None
    procedures_performed: Optional[List[str]] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[date] = None
    follow_up_notes: Optional[str] = None
    status: Optional[VisitStatus] = None

class VisitInDB(VisitBase):
    """Visit from database"""
    id: int
    tenant_id: int
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int]
    visit_code: str
    visit_date: datetime
    status: VisitStatus
    diagnosis_codes: List[str]
    prescriptions: List[Dict[str, Any]]
    lab_tests_ordered: List[Dict[str, Any]]
    procedures_performed: List[str]
    follow_up_required: bool
    follow_up_date: Optional[date]
    follow_up_notes: Optional[str]
    attachments: List[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

class Visit(VisitInDB):
    """Public visit schema"""
    patient: 'Patient'
    doctor: 'Doctor'

class VisitWithDetails(Visit):
    """Visit with full details including billing"""
    invoice: Optional['Invoice'] = None
    visit_services: List['VisitService'] = []