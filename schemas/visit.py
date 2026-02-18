from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import date, datetime
from models.visit import VisitStatus

if TYPE_CHECKING:
    from schemas.patient import Patient
    from schemas.doctor import Doctor
    from schemas.billing import VisitService, Invoice

class Vitals(BaseModel):
    """Patient vitals"""
    model_config = ConfigDict(extra='forbid')

    blood_pressure: Optional[str] = Field(None, pattern=r'^\d{2,3}/\d{2,3}$')
    temperature: Optional[float] = Field(None, ge=90, le=110)
    pulse: Optional[int] = Field(None, ge=30, le=200)
    respiratory_rate: Optional[int] = Field(None, ge=8, le=40)
    oxygen_saturation: Optional[int] = Field(None, ge=70, le=100)
    weight: Optional[float] = Field(None, ge=0, le=500)
    height: Optional[float] = Field(None, ge=0, le=300)
    bmi: Optional[float] = None
    
    @model_validator(mode='after')
    def calculate_bmi(self):
        # Only calculate if BMI is not explicitly provided and weight/height exist
        if self.bmi is None and self.weight and self.height and self.height > 0:
            height_m = self.height / 100
            self.bmi = round(self.weight / (height_m ** 2), 2)
        return self

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
    # FIX: Mutable default fixed with default_factory
    symptoms: List[str] = Field(default_factory=list)
    vitals: Optional[Vitals] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class VisitCreate(VisitBase):
    """Create visit schema"""
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int] = None
    # FIX: Mutable defaults fixed with default_factory
    prescriptions: List[Prescription] = Field(default_factory=list)
    lab_tests_ordered: List[LabTest] = Field(default_factory=list)
    procedures_performed: List[str] = Field(default_factory=list)
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
    # NOTE: Status transitions (e.g., completed -> in_progress) should be 
    # enforced in the service layer, not just here.
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
    diagnosis_codes: List[str] = Field(default_factory=list)
    # DB returns JSON as dict/list, schema accepts Any for flexibility
    prescriptions: List[Dict[str, Any]] = Field(default_factory=list)
    lab_tests_ordered: List[Dict[str, Any]] = Field(default_factory=list)
    procedures_performed: List[str] = Field(default_factory=list)
    follow_up_required: bool
    follow_up_date: Optional[date]
    follow_up_notes: Optional[str]
    attachments: List[str] = Field(default_factory=list)
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
    visit_services: List['VisitService'] = Field(default_factory=list)