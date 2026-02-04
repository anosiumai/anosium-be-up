from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.tenant import (
    Tenant, TenantCreate, TenantUpdate, TenantWithStats,
    SubscriptionUpdate
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.tenant_service import TenantService
from models.user import User, UserRole
from models.tenant import SubscriptionTier, SubscriptionStatus

router = APIRouter()

@router.post("", response_model=Tenant, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_in: TenantCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Create new tenant (clinic) with admin user
    
    **Public endpoint** - Used for clinic registration
    
    **Creates:**
    - Tenant record
    - Clinic admin user
    - Default settings and features based on tier
    """
    service = TenantService(db)
    
    try:
        tenant = service.create_tenant(tenant_in)
        return tenant
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Tenant])
async def list_tenants(
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    subscription_tier: Optional[SubscriptionTier] = None,
    subscription_status: Optional[SubscriptionStatus] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None, min_length=2)
):
    """
    Get list of all tenants
    
    **Required Permissions:** Super Admin only
    
    **Filters:**
    - subscription_tier: Filter by subscription tier
    - subscription_status: Filter by subscription status
    - is_active: Filter active/inactive tenants
    - search: Search by name, slug, or email
    """
    service = TenantService(db)
    
    filters = {}
    if subscription_tier:
        filters["subscription_tier"] = subscription_tier
    if subscription_status:
        filters["subscription_status"] = subscription_status
    if is_active is not None:
        filters["is_active"] = is_active
    
    result = service.get_tenants(
        skip=pagination["skip"],
        limit=pagination["limit"],
        search=search,
        filters=filters
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/me", response_model=Tenant)
async def get_my_tenant(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get current user's tenant information
    """
    return current_tenant

@router.get("/me/stats", response_model=TenantWithStats)
async def get_my_tenant_stats(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get current tenant with statistics
    
    **Includes:**
    - Total patients
    - Total doctors
    - Total appointments
    - Monthly revenue
    - Active users
    """
    service = TenantService(db)
    tenant_stats = service.get_tenant_with_stats(current_tenant.id)
    
    if not tenant_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant_stats

@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: int,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Get tenant by ID
    
    **Required Permissions:** Super Admin only
    """
    service = TenantService(db)
    tenant = service.get_tenant(tenant_id)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant

@router.get("/{tenant_id}/stats", response_model=TenantWithStats)
async def get_tenant_stats(
    tenant_id: int,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Get tenant with statistics
    
    **Required Permissions:** Super Admin only
    """
    service = TenantService(db)
    tenant_stats = service.get_tenant_with_stats(tenant_id)
    
    if not tenant_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant_stats

@router.put("/me", response_model=Tenant)
async def update_my_tenant(
    tenant_in: TenantUpdate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update current tenant information
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Updatable fields:**
    - Name, contact info, address
    - Logo and branding
    - Settings
    """
    service = TenantService(db, current_user.id)
    
    tenant = service.update_tenant(current_tenant.id, tenant_in)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant

@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: int,
    tenant_in: TenantUpdate,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Update tenant information (Super Admin)
    
    **Required Permissions:** Super Admin only
    """
    service = TenantService(db, current_user.id)
    
    tenant = service.update_tenant(tenant_id, tenant_in)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant

@router.put("/{tenant_id}/subscription", response_model=Tenant)
async def update_tenant_subscription(
    tenant_id: int,
    subscription_in: SubscriptionUpdate,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Update tenant subscription tier and features
    
    **Required Permissions:** Super Admin only
    
    **Updates:**
    - Subscription tier (free, basic, premium, enterprise)
    - Subscription status
    - Enabled features
    - Subscription dates
    """
    service = TenantService(db, current_user.id)
    
    try:
        tenant = service.update_subscription(tenant_id, subscription_in)
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return tenant
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{tenant_id}/activate", response_model=SuccessResponse)
async def activate_tenant(
    tenant_id: int,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Activate tenant
    
    **Required Permissions:** Super Admin only
    """
    service = TenantService(db, current_user.id)
    
    success = service.activate_tenant(tenant_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Tenant activated successfully"
    )

@router.post("/{tenant_id}/deactivate", response_model=SuccessResponse)
async def deactivate_tenant(
    tenant_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Deactivate tenant (suspend access)
    
    **Required Permissions:** Super Admin only
    
    **Effect:**
    - Prevents all users from logging in
    - Disables all API access
    - Data remains intact for reactivation
    """
    service = TenantService(db, current_user.id)
    
    success = service.deactivate_tenant(tenant_id, reason=reason)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Tenant deactivated successfully"
    )

@router.delete("/{tenant_id}", response_model=SuccessResponse)
async def delete_tenant(
    tenant_id: int,
    confirm: bool = Query(..., description="Must be true to confirm deletion"),
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Delete tenant and all associated data
    
    **Required Permissions:** Super Admin only
    
    **WARNING:** This action is irreversible!
    
    **Deletes:**
    - Tenant record
    - All users
    - All patients
    - All appointments
    - All visits
    - All billing records
    - All other associated data
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm deletion"
        )
    
    service = TenantService(db, current_user.id)
    
    success = service.delete_tenant(tenant_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Tenant deleted successfully"
    )

@router.get("/{tenant_id}/usage", response_model=dict)
async def get_tenant_usage(
    tenant_id: int,
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Get tenant resource usage and limits
    
    **Required Permissions:** Super Admin only
    
    **Returns:**
    - Current usage vs limits
    - Feature usage statistics
    - API usage metrics
    """
    service = TenantService(db)
    
    usage = service.get_tenant_usage(tenant_id)
    
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return usage

@router.post("/{tenant_id}/check-feature", response_model=dict)
async def check_feature_access(
    tenant_id: int,
    feature: str = Query(..., description="Feature name to check"),
    current_user: User = Depends(deps.require_super_admin),
    db: Session = Depends(deps.get_db)
):
    """
    Check if tenant has access to specific feature
    
    **Required Permissions:** Super Admin only
    """
    service = TenantService(db)
    
    has_access = service.check_feature_access(tenant_id, feature)
    
    return {
        "tenant_id": tenant_id,
        "feature": feature,
        "has_access": has_access
    }

@router.get("/slug/{slug}", response_model=Tenant)
async def get_tenant_by_slug(
    slug: str,
    db: Session = Depends(deps.get_db)
):
    """
    Get tenant by slug (public endpoint for login page)
    
    **Use case:** Determine which tenant's login page to show
    """
    service = TenantService(db)
    tenant = service.get_tenant_by_slug(slug)
    
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Return only public information
    return Tenant(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        is_active=tenant.is_active
    )