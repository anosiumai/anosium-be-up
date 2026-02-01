"""
Service-related Pydantic Schemas
Handles service creation, updates, and responses
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(gt=0)
    tax_percentage: float = Field(ge=0, le=100, default=0.0)
    category: Optional[str] = None
    is_package: bool = False

class ServiceCreate(ServiceBase):
    pass

class ServiceResponse(ServiceBase):
    id: int
    clinic_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True