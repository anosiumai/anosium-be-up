from pydantic import BaseModel, EmailStr, Field, validator
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from datetime import datetime
from models.ai_lead import LeadSource, LeadStatus

if TYPE_CHECKING:
    from schemas.user import User
    from schemas.patient import Patient, PatientCreate


class AIInteractionCreate(BaseModel):
    """Create AI interaction"""
    message_type: str = Field(..., pattern=r'^(user|bot)$')
    message_content: str = Field(..., min_length=1)
    platform: str
    intent_detected: Optional[str] = None
    entities_extracted: Optional[Dict[str, Any]] = None


class AIInteraction(BaseModel):
    """AI chatbot interaction"""
    id: int
    lead_id: int
    message_type: str
    message_content: str
    platform: str
    timestamp: datetime
    intent_detected: Optional[str]
    entities_extracted: Dict[str, Any]
    
    class Config:
        from_attributes = True


class AILeadBase(BaseModel):
    """Base AI lead schema"""
    name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    email: Optional[EmailStr] = None
    source: LeadSource
    message: Optional[str] = None
    interested_in: Optional[str] = None
    
    class Config:
        from_attributes = True


class AILeadCreate(AILeadBase):
    """Create AI lead schema"""
    source_details: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    ai_sentiment: Optional[str] = None
    ai_intent: Optional[str] = None
    ai_suggested_action: Optional[str] = None


class AILeadUpdate(BaseModel):
    """Update AI lead schema"""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[LeadStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[List[str]] = None
    interested_in: Optional[str] = None
    next_follow_up_at: Optional[datetime] = None
    assigned_to: Optional[int] = None


class LeadConversion(BaseModel):
    """Convert lead to patient"""
    create_patient: bool = True
    patient_data: Optional[Dict[str, Any]] = None  # Changed from PatientCreate to Dict
    conversion_notes: Optional[str] = None


class AILeadInDB(AILeadBase):
    """AI lead from database"""
    id: int
    tenant_id: int
    patient_id: Optional[int]
    source_details: Dict[str, Any]
    tags: List[str]
    status: LeadStatus
    priority: int
    ai_sentiment: Optional[str]
    ai_intent: Optional[str]
    ai_suggested_action: Optional[str]
    last_contacted_at: Optional[datetime]
    next_follow_up_at: Optional[datetime]
    follow_up_count: int
    converted_at: Optional[datetime]
    conversion_notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    assigned_to: Optional[int]


class AILead(AILeadInDB):
    """Public AI lead schema"""
    patient: Optional['Patient'] = None
    assigned_user: Optional['User'] = None


class AILeadWithInteractions(AILead):
    """AI lead with interaction history"""
    interactions: List[AIInteraction] = []
    total_interactions: int = 0
    last_interaction: Optional[datetime] = None


# Resolve forward references after all schemas are defined
from schemas.patient import Patient, PatientCreate
from schemas.user import User

AILead.model_rebuild()
AILeadWithInteractions.model_rebuild()
