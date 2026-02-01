"""
FastAPI Routes for AI Automation & Chatbot
Handles lead management, chatbot interactions, and automation
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from core.database import get_db
from schemas.doctor import LeadCreate, LeadUpdate, LeadResponse, ChatbotMessage, ChatbotResponse
from schemas.doctor import AIInteractionResponse
from schemas.common import MessageResponse
from schemas.clinic import ClinicUpdate
from services.ai_service import AIAutomationService
from services.multi_clinic import MultiClinicService
from core.security import get_current_user, require_clinic_access
from models.user import User
from models.base import UserRole, LeadStatus, LeadSource
from models.lead import Lead
from models.ai_interaction import AIInteraction

router = APIRouter(prefix="/api/ai", tags=["AI Automation"])


# ==================== CHATBOT ====================
@router.post("/{clinic_id}/chatbot", response_model=ChatbotResponse)
async def chatbot_interaction(
    clinic_id: int,
    message: ChatbotMessage,
    db: Session = Depends(get_db)
):
    """
    Public chatbot endpoint
    Processes user messages and generates AI responses
    No authentication required for chatbot
    """
    # Check if clinic exists and is active
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    if not MultiClinicService.is_subscription_active(clinic):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic subscription is not active"
        )
    
    response = AIAutomationService.process_chatbot_message(db, clinic_id, message)
    return response


@router.post("/{clinic_id}/chatbot/whatsapp", response_model=ChatbotResponse)
async def whatsapp_webhook(
    clinic_id: int,
    message: ChatbotMessage,
    db: Session = Depends(get_db)
):
    """
    WhatsApp webhook endpoint
    Integrates with WhatsApp Business API
    """
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    # Check WhatsApp integration feature
    if not MultiClinicService.check_feature_access(clinic, "whatsapp_integration"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WhatsApp integration not available in current subscription"
        )
    
    message.platform = LeadSource.WHATSAPP
    response = AIAutomationService.process_chatbot_message(db, clinic_id, message)
    return response


# ==================== LEADS ====================
@router.post("/{clinic_id}/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    clinic_id: int,
    lead_data: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Create a lead manually"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check AI automation feature
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not MultiClinicService.check_feature_access(clinic, "ai_automation"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI automation not available in current subscription"
        )
    
    lead = AIAutomationService.create_lead_manually(db, clinic_id, lead_data)
    return lead


@router.get("/{clinic_id}/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    clinic_id: int,
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get lead by ID"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.clinic_id == clinic_id
    ).first()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead


@router.get("/{clinic_id}/leads", response_model=List[LeadResponse])
async def list_leads(
    clinic_id: int,
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    from_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """List leads with filters"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    leads = AIAutomationService.list_leads(
        db, clinic_id, status, source, from_date, skip, limit
    )
    return leads


@router.put("/{clinic_id}/leads/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    clinic_id: int,
    lead_id: int,
    new_status: LeadStatus,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Update lead status"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    lead = AIAutomationService.update_lead_status(
        db, clinic_id, lead_id, new_status, notes
    )
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead


@router.post("/{clinic_id}/leads/{lead_id}/convert", response_model=MessageResponse)
async def convert_lead_to_patient(
    clinic_id: int,
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Convert lead to patient"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check patient limit
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    limit_check = MultiClinicService.check_limit(db, clinic, "patients")
    
    if not limit_check["can_add"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Patient limit reached ({limit_check['current']}/{limit_check['limit']}). Upgrade subscription."
        )
    
    patient = AIAutomationService.convert_lead_to_patient(db, clinic_id, lead_id)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found or already converted"
        )
    
    return MessageResponse(
        message=f"Lead converted to patient successfully. Patient ID: {patient.id}"
    )


@router.get("/{clinic_id}/leads/followup/pending", response_model=List[LeadResponse])
async def get_leads_for_followup(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get leads that need follow-up"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    leads = AIAutomationService.get_leads_for_follow_up(db, clinic_id)
    return leads


@router.post("/{clinic_id}/leads/{lead_id}/followup", response_model=LeadResponse)
async def schedule_followup(
    clinic_id: int,
    lead_id: int,
    follow_up_date: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Schedule follow-up for a lead"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    lead = AIAutomationService.schedule_follow_up(
        db, clinic_id, lead_id, follow_up_date
    )
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead


# ==================== STATISTICS ====================
@router.get("/{clinic_id}/stats")
async def get_ai_stats(
    clinic_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """
    Get AI automation statistics
    Includes interactions, leads, conversion rates
    """
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check analytics feature
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not MultiClinicService.check_feature_access(clinic, "analytics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analytics not available in current subscription"
        )
    
    stats = AIAutomationService.get_ai_stats(db, clinic_id, days)
    return stats


# ==================== AI CONFIGURATION ====================
@router.post("/{clinic_id}/config/ai", response_model=MessageResponse)
async def update_ai_config(
    clinic_id: int,
    enabled: bool = True,
    auto_respond: bool = False,
    lead_capture: bool = True,
    appointment_booking: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Update AI automation configuration"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check AI automation feature
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not MultiClinicService.check_feature_access(clinic, "ai_automation"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI automation not available in current subscription"
        )
    
    clinic_update = ClinicUpdate(
        ai_config={
            "enabled": enabled,
            "auto_respond": auto_respond,
            "lead_capture": lead_capture,
            "appointment_booking": appointment_booking,
            "response_tone": clinic.ai_config.get("response_tone", "professional"),
            "working_hours": clinic.ai_config.get("working_hours", {})
        }
    )
    
    MultiClinicService.update_clinic(db, clinic_id, clinic_update)
    
    return MessageResponse(message="AI configuration updated successfully")


# ==================== INTERACTIONS ====================
@router.get("/{clinic_id}/interactions", response_model=List[AIInteractionResponse])
async def list_interactions(
    clinic_id: int,
    lead_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """List AI interactions"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    from sqlalchemy import and_
    
    query = db.query(AIInteraction).filter(AIInteraction.clinic_id == clinic_id)
    
    if lead_id:
        query = query.filter(AIInteraction.lead_id == lead_id)
    
    interactions = query.order_by(AIInteraction.created_at.desc()).offset(skip).limit(limit).all()
    return interactions