# 📁 api/v1/endpoints/ai_leads.py
from fastapi import APIRouter, Depends, HTTPException, status, Request  # ← add Request
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.ai_lead import (
    AILead, AILeadCreate, AILeadUpdate, AILeadWithInteractions,
    AIInteractionCreate, LeadConversion
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.ai_lead_service import AILeadService
from models.user import User, UserRole
from models.tenant import Tenant
from models.ai_lead import LeadStatus
from core.limiter import limiter

router = APIRouter()

@router.post("", response_model=AILead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_lead(
    request: Request,
    lead_in: AILeadCreate,
    current_tenant: Tenant = Depends(deps.require_api_key_or_jwt),
    db: Session = Depends(deps.get_db)
):
    """
    Create new AI-captured lead
    
    **Note:** This endpoint can be called by AI chatbots (with API key)
    or by authenticated users
    """
    service = AILeadService(db, current_tenant.id)
    
    try:
        lead = service.create_lead(lead_in)
        return lead
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[AILead])
async def list_leads(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    status: Optional[LeadStatus] = None,
    source: Optional[str] = None,
    assigned_to: Optional[int] = None
):
    """
    Get list of AI leads with filtering
    """
    service = AILeadService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if status:
        filters["status"] = status
    if source:
        filters["source"] = source
    if assigned_to:
        filters["assigned_to"] = assigned_to
    
    result = service.get_leads(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters=filters
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/{lead_id}", response_model=AILeadWithInteractions)
async def get_lead(
    lead_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get lead with conversation history
    """
    service = AILeadService(db, current_tenant.id, current_user.id)
    lead = service.get_lead_with_interactions(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead

@router.put("/{lead_id}", response_model=AILead)
async def update_lead(
    lead_id: int,
    lead_in: AILeadUpdate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update lead information
    """
    service = AILeadService(db, current_tenant.id, current_user.id)
    
    lead = service.update_lead(lead_id, lead_in)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead

@router.post("/{lead_id}/interactions", response_model=SuccessResponse)
@limiter.limit("60/minute")
async def add_interaction(
    request: Request,
    lead_id: int,
    interaction_in: AIInteractionCreate,
    current_tenant: Tenant = Depends(deps.require_api_key_or_jwt),
    db: Session = Depends(deps.get_db)
):
    """
    Add AI chatbot interaction to lead
    """
    service = AILeadService(db, current_tenant.id)
    
    try:
        service.add_interaction(lead_id, interaction_in)
        return SuccessResponse(
            success=True,
            message="Interaction added successfully"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{lead_id}/convert", response_model=SuccessResponse)
async def convert_lead(
    lead_id: int,
    conversion_data: LeadConversion,
    current_user: User = Depends(deps.require_any_role([UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Convert lead to patient
    
    **Required Permissions:** Receptionist, Clinic Admin, or Super Admin
    """
    service = AILeadService(db, current_tenant.id, current_user.id)
    
    try:
        patient = service.convert_to_patient(lead_id, conversion_data)
        
        return SuccessResponse(
            success=True,
            message="Lead converted to patient successfully",
            data={"patient_id": patient.id}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{lead_id}/assign", response_model=SuccessResponse)
async def assign_lead(
    lead_id: int,
    user_id: int,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Assign lead to team member
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = AILeadService(db, current_tenant.id, current_user.id)
    
    success = service.assign_lead(lead_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Lead assigned successfully"
    )