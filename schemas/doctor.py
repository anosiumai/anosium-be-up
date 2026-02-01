from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"

class LeadSource(str, Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    WALK_IN = "walk_in"

class LeadCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    source: LeadSource
    initial_message: Optional[str] = None
    intent: Optional[str] = None
    preferred_doctor: Optional[str] = None
    preferred_date: Optional[datetime] = None
    service_interest: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[LeadStatus] = None
    intent: Optional[str] = None
    preferred_doctor: Optional[str] = None
    preferred_date: Optional[datetime] = None
    service_interest: Optional[str] = None
    next_follow_up: Optional[datetime] = None

class LeadResponse(BaseModel):
    id: int
    clinic_id: int
    name: str
    phone: str
    email: Optional[str]
    source: str
    status: str
    initial_message: Optional[str]
    conversation_history: List[Dict[str, Any]]
    ai_responses: int
    intent: Optional[str]
    preferred_doctor: Optional[str]
    preferred_date: Optional[datetime]
    service_interest: Optional[str]
    converted_to_patient: bool
    patient_id: Optional[int]
    last_contacted: Optional[datetime]
    next_follow_up: Optional[datetime]
    follow_up_count: int
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True

class AIInteractionCreate(BaseModel):
    lead_id: Optional[int] = None
    platform: str
    message_type: str = "text"
    user_message: str
    ai_response: Optional[str] = None
    intent_detected: Optional[str] = None
    entities_extracted: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    action_taken: Optional[str] = None

class AIInteractionResponse(BaseModel):
    id: int
    clinic_id: int
    lead_id: Optional[int]
    platform: str
    message_type: str
    user_message: str
    ai_response: Optional[str]
    intent_detected: Optional[str]
    entities_extracted: Dict[str, Any]
    confidence_score: Optional[float]
    action_taken: Optional[str]
    response_time_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class ChatbotMessage(BaseModel):
    message: str
    phone: Optional[str] = None
    name: Optional[str] = None
    platform: LeadSource = LeadSource.WEBSITE
    metadata: Optional[Dict[str, Any]] = None

class ChatbotResponse(BaseModel):
    response: str
    lead_id: Optional[int] = None
    action_taken: Optional[str] = None
    confidence: float
    next_steps: List[str] = []

class AutomationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_conditions: Dict[str, Any]
    action_type: str
    action_config: Dict[str, Any]
    priority: int = 0

class AutomationRuleResponse(BaseModel):
    id: int
    clinic_id: int
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_conditions: Dict[str, Any]
    action_type: str
    action_config: Dict[str, Any]
    is_active: bool
    priority: int
    execution_count: int
    last_executed: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True