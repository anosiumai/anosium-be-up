from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    
    from schemas.doctor import Doctor

class DepartmentBase(BaseModel):
    """Base department schema"""
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=20, regex=r'^[A-Z0-9_]+$')
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class DepartmentCreate(DepartmentBase):
    """Create department schema"""
    head_doctor_id: Optional[int] = None

class DepartmentUpdate(BaseModel):
    """Update department schema"""
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = None
    head_doctor_id: Optional[int] = None
    is_active: Optional[bool] = None

class DepartmentInDB(DepartmentBase):
    """Department from database"""
    id: int
    tenant_id: int
    head_doctor_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class Department(DepartmentInDB):
    """Public department schema"""
    head_doctor: Optional['Doctor'] = None

class DepartmentWithDoctors(Department):
    """Department with doctors list"""
    doctors: List['Doctor'] = []
    total_doctors: int = 0
    active_doctors: int = 0