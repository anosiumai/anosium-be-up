from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from models.audit import AuditAction  # Import enum from models

if TYPE_CHECKING:
    from schemas.user import User
    from schemas.patient import Patient

class AuditLogBase(BaseModel):
    """Base audit log schema"""
    action: AuditAction
    resource_type: str
    resource_id: int
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changes_summary: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class AuditLogInDB(AuditLogBase):
    """Audit log from database"""
    id: int
    tenant_id: int
    user_id: Optional[int]
    request_id: Optional[str]
    created_at: datetime

class AuditLog(AuditLogInDB):
    """Public audit log schema"""
    user: Optional['User'] = None

class DataAccessLogBase(BaseModel):
    """Base data access log schema"""
    access_type: str
    accessed_fields: Optional[List[str]] = None
    purpose: Optional[str] = None
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True

class DataAccessLogInDB(DataAccessLogBase):
    """Data access log from database"""
    id: int
    tenant_id: int
    user_id: int
    patient_id: int
    accessed_at: datetime

class DataAccessLog(DataAccessLogInDB):
    """Public data access log schema"""
    user: Optional['User'] = None
    patient: Optional['Patient'] = None