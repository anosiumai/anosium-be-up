from pydantic import BaseModel, Field, validator
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from models.service import ServiceType
from pydantic import model_validator

if TYPE_CHECKING:
    from schemas.department import Department

class ServiceBase(BaseModel):
    """Base service schema"""
    code: str = Field(..., min_length=2, max_length=50, pattern=r'^[A-Z0-9_]+$')
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    service_type: ServiceType
    base_price: int = Field(..., ge=0)
    tax_percentage: int = Field(default=0, ge=0, le=100)
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)

    @validator('service_type', pre=True)
    def normalize_service_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    class Config:
        from_attributes = True

class ServiceCreate(ServiceBase):
    """Create service schema"""
    department_id: Optional[int] = None

class ServiceUpdate(BaseModel):
    """Update service schema"""
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    service_type: Optional[ServiceType] = None
    base_price: Optional[int] = Field(None, ge=0)
    tax_percentage: Optional[int] = Field(None, ge=0, le=100)
    estimated_duration_minutes: Optional[int] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceInDB(ServiceBase):
    """Service from database"""
    id: int
    tenant_id: int
    department_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class Service(ServiceInDB):
    """Public service schema"""
    department: Optional['Department'] = None
    final_price: int = 0

    @model_validator(mode='after')
    def compute_final_price(self):
        self.final_price = self.base_price + (self.base_price * self.tax_percentage // 100)
        return self

class PackageServiceItem(BaseModel):
    """Service item in a package"""
    service_id: int
    quantity: int = Field(default=1, ge=1)

class PackageBase(BaseModel):
    """Base package schema"""
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    total_price: int = Field(..., ge=0)
    discount_percentage: int = Field(default=0, ge=0, le=100)
    validity_days: Optional[int] = Field(None, ge=1)
    
    class Config:
        from_attributes = True

class PackageCreate(PackageBase):
    """Create package schema"""
    services: List[PackageServiceItem] = Field(..., min_items=1)

class PackageUpdate(BaseModel):
    """Schema for updating a package"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    package_price: Optional[int] = Field(None, ge=0)
    discount_percentage: Optional[int] = Field(None, ge=0, le=100)
    validity_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    service_ids: Optional[List[int]] = None
    
    class Config:
        from_attributes = True

class PackageInDB(PackageBase):
    """Package from database"""
    id: int
    tenant_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class Package(PackageInDB):
    """Public package schema"""
    services: List['Service'] = []
    discounted_price: int
    savings: int
    
    @validator('discounted_price', pre=True, always=True)
    def calculate_discounted_price(cls, v, values):
        total = values.get('total_price', 0)
        discount = values.get('discount_percentage', 0)
        return total - (total * discount // 100)
    
    @validator('savings', pre=True, always=True)
    def calculate_savings(cls, v, values):
        total = values.get('total_price', 0)
        discount = values.get('discount_percentage', 0)
        return total * discount // 100


class PackageWithServices(Package):
    """Package with detailed service information"""
    services: List[dict] = []
    savings: int = 0
    total_individual_price: int = 0
    

class ServiceStatistics(BaseModel):
    """Service statistics"""
    total_services: int
    active_services: int
    inactive_services: int
    by_type: dict
    price_range: dict


class PackageStatistics(BaseModel):
    """Package statistics"""
    total_packages: int
    active_packages: int
    inactive_packages: int