"""
User-related Pydantic Schemas
Handles user creation, updates, and responses
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CLINIC_ADMIN = "clinic_admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF = "staff"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    specialization: Optional[str] = None
    license_number: Optional[str] = None

class UserCreate(UserBase):
    password: str
    clinic_id: int

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    clinic_id: int
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True