from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from models.user import UserRole

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    role: UserRole
    
    class Config:
        from_attributes = True

class UserCreate(UserBase):
    """Create user schema"""
    password: str = Field(..., min_length=8)
    tenant_id: Optional[int] = None  # Set by system for non-super-admins
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v

class UserUpdate(BaseModel):
    """Update user schema"""
    first_name: Optional[str] = Field(None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    """Login credentials"""
    email: EmailStr
    password: str

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    """Token payload data"""
    user_id: int
    tenant_id: Optional[int]
    role: UserRole
    email: str

class PasswordReset(BaseModel):
    """Password reset request"""
    email: EmailStr

class PasswordChange(BaseModel):
    """Change password"""
    old_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_password(cls, v, values):
        if 'old_password' in values and v == values['old_password']:
            raise ValueError('New password must be different')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v

class UserInDB(UserBase):
    """User from database"""
    id: int
    tenant_id: Optional[int]
    avatar_url: Optional[str]
    permissions: Dict[str, Any]
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

class User(UserInDB):
    """Public user schema"""
    full_name: str
    
    @validator('full_name', pre=True, always=True)
    def set_full_name(cls, v, values):
        return f"{values.get('first_name', '')} {values.get('last_name', '')}".strip()

class ResetPasswordBody(BaseModel):
    """Admin reset password body"""
    new_password: str = Field(..., min_length=8)