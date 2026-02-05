from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime, time
from models.notification import NotificationType, NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from schemas.user import User
    from schemas.patient import Patient


class NotificationBase(BaseModel):
    """Base notification schema"""
    type: NotificationType
    channel: NotificationChannel
    subject: Optional[str] = Field(None, max_length=500)
    message: str = Field(..., min_length=1)
    
    class Config:
        from_attributes = True

class NotificationCreate(NotificationBase):
    """Create notification schema"""
    user_id: Optional[int] = None
    patient_id: Optional[int] = None
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    template_id: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class BulkNotificationCreate(BaseModel):
    """Create bulk notifications"""
    type: NotificationType
    channel: NotificationChannel
    template_id: str
    recipient_filters: Dict[str, Any]  # Criteria to select recipients
    scheduled_for: Optional[datetime] = None

class NotificationInDB(NotificationBase):
    """Notification from database"""
    id: int
    tenant_id: int
    user_id: Optional[int]
    patient_id: Optional[int]
    recipient_email: Optional[str]
    recipient_phone: Optional[str]
    template_id: Optional[str]
    template_variables: Dict[str, Any]
    status: NotificationStatus
    scheduled_for: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    failed_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    external_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

class Notification(NotificationInDB):
    """Public notification schema"""
    user: Optional['User'] = None
    patient: Optional['Patient'] = None

class NotificationTemplateBase(BaseModel):
    """Base notification template schema"""
    code: str = Field(..., min_length=2, max_length=100, pattern=r'^[A-Z0-9_]+$')
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    type: NotificationType
    channel: NotificationChannel
    subject_template: Optional[str] = None
    body_template: str = Field(..., min_length=1)
    language: str = Field(default="en", pattern=r'^[a-z]{2}$')
    
    class Config:
        from_attributes = True

class NotificationTemplateCreate(NotificationTemplateBase):
    """Create notification template"""
    pass

class NotificationTemplate(NotificationTemplateBase):
    """Notification template"""
    id: int
    tenant_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class NotificationPreference(BaseModel):
    """Notification preferences"""
    email_enabled: bool = True
    sms_enabled: bool = True
    whatsapp_enabled: bool = True
    push_enabled: bool = True
    enabled_types: Dict[str, bool] = {}
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: str = "UTC"
    
    class Config:
        from_attributes = True

class NotificationPreferenceUpdate(BaseModel):
    """Update notification preferences"""
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    enabled_types: Optional[Dict[str, bool]] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: Optional[str] = None