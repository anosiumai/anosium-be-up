"""
Authentication Pydantic Schemas
Handles login, tokens, and authentication responses
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CLINIC_ADMIN = "clinic_admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF = "staff"

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict  # Will be UserResponse
    clinic: dict  # Will be ClinicResponse