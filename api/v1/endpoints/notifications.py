from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.notification import (
    Notification, NotificationCreate, BulkNotificationCreate,
    NotificationTemplate, NotificationTemplateCreate,
    NotificationPreference, NotificationPreferenceUpdate
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.notification_service import NotificationService
from models.user import User
from models.tenant import Tenant
from models.notification import NotificationStatus, NotificationType

router = APIRouter()

# ========== NOTIFICATIONS ==========

@router.post("", response_model=Notification, status_code=status.HTTP_201_CREATED)
async def send_notification(
    notification_in: NotificationCreate,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Send notification to user or patient
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    try:
        notification = service.send_notification(notification_in)
        return notification
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/bulk", response_model=SuccessResponse)
async def send_bulk_notifications(
    bulk_notification: BulkNotificationCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Send bulk notifications to multiple recipients
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    try:
        count = service.send_bulk_notifications(bulk_notification)
        
        return SuccessResponse(
            success=True,
            message=f"Scheduled {count} notifications successfully"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Notification])
async def list_notifications(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    notification_type: Optional[NotificationType] = None,
    status: Optional[NotificationStatus] = None
):
    """
    Get list of notifications
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if notification_type:
        filters["type"] = notification_type
    if status:
        filters["status"] = status
    
    result = service.get_notifications(
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

@router.get("/me", response_model=List[Notification])
async def get_my_notifications(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    unread_only: bool = False,
    limit: int = 20
):
    """
    Get current user's notifications
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    notifications = service.get_user_notifications(
        current_user.id,
        unread_only=unread_only,
        limit=limit
    )
    
    return notifications

@router.post("/{notification_id}/mark-read", response_model=SuccessResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Mark notification as read
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    success = service.mark_as_read(notification_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Notification marked as read"
    )

@router.post("/mark-all-read", response_model=SuccessResponse)
async def mark_all_notifications_read(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Mark all user's notifications as read
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    count = service.mark_all_as_read(current_user.id)
    
    return SuccessResponse(
        success=True,
        message=f"Marked {count} notifications as read"
    )

# ========== TEMPLATES ==========

@router.post("/templates", response_model=NotificationTemplate, status_code=status.HTTP_201_CREATED)
async def create_notification_template(
    template_in: NotificationTemplateCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create notification template
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    try:
        template = service.create_template(template_in)
        return template
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/templates", response_model=List[NotificationTemplate])
async def list_notification_templates(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    is_active: bool = True
):
    """
    Get list of notification templates
    """
    service = NotificationService(db, current_tenant.id, current_user.id)
    
    templates = service.get_templates(filters={"is_active": is_active})
    return templates

# ========== PREFERENCES ==========

@router.get("/preferences", response_model=NotificationPreference)
async def get_notification_preferences(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Get current user's notification preferences
    """
    service = NotificationService(db)
    
    preferences = service.get_user_preferences(current_user.id)
    return preferences

@router.put("/preferences", response_model=NotificationPreference)
async def update_notification_preferences(
    preferences_in: NotificationPreferenceUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Update notification preferences
    """
    service = NotificationService(db)
    
    preferences = service.update_user_preferences(current_user.id, preferences_in)
    return preferences