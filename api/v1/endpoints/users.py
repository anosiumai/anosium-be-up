# api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.user import User, UserCreate, UserUpdate
from schemas.common import PaginatedResponse, SuccessResponse
from services.user_service import UserService
from models.user import User as UserModel, UserRole
from models.tenant import Tenant

router = APIRouter()

@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new user in tenant
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Roles that can be created:**
    - Doctor
    - Receptionist
    - Staff
    - Accountant
    - Clinic Admin (only by Super Admin)
    """
    # Validate role permissions
    if user_in.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create super admin users via this endpoint"
        )
    
    if user_in.role == UserRole.CLINIC_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create clinic admin users"
        )
    
    service = UserService(db, current_tenant.id, current_user.id)
    
    try:
        # Set tenant_id for non-super-admin users
        if not user_in.tenant_id:
            user_in.tenant_id = current_tenant.id
        
        user = service.create_user(user_in)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[User])
async def list_users(
    current_user: UserModel = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None, min_length=2)
):
    """
    Get list of users in tenant
    
    **Filters:**
    - role: Filter by user role
    - is_active: Filter active/inactive users
    - search: Search by name or email
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if role:
        filters["role"] = role
    if is_active is not None:
        filters["is_active"] = is_active
    
    result = service.get_users(
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

@router.get("/me", response_model=User)
async def get_current_user_profile(
    current_user: UserModel = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Get current user's profile
    """
    return current_user

@router.put("/me", response_model=User)
async def update_current_user_profile(
    user_in: UserUpdate,
    current_user: UserModel = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Update current user's profile
    
    **Users can update:**
    - First name, last name
    - Phone number
    - Avatar
    
    **Cannot update:**
    - Email
    - Role
    - Permissions
    """
    service = UserService(db, current_user.tenant_id, current_user.id)
    
    # Prevent users from changing sensitive fields
    if user_in.permissions is not None or user_in.is_active is not None:
        if current_user.role not in [UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update these fields"
            )
    
    user = service.update_user(current_user.id, user_in)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/roles", response_model=List[str])
async def get_available_roles(
    current_user: UserModel = Depends(deps.get_current_user)
):
    """
    Get list of available user roles
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return [role.value for role in UserRole]
    else:
        # Clinic admins cannot create super admins
        return [
            role.value for role in UserRole 
            if role != UserRole.SUPER_ADMIN
        ]

@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    current_user: UserModel = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get user by ID
    """
    service = UserService(db, current_tenant.id, current_user.id)
    user = service.get_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user belongs to same tenant (unless super admin)
    if current_user.role != UserRole.SUPER_ADMIN:
        if user.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    return user

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update user
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    # Check if target user belongs to same tenant
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if current_user.role != UserRole.SUPER_ADMIN:
        if target_user.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update users from other tenants"
            )
        
        # Prevent clinic admins from modifying super admins
        if target_user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update super admin users"
            )
    
    user = service.update_user(user_id, user_in)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.delete("/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: int,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete user (soft delete)
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Note:** User is deactivated, not permanently deleted
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Check if target user belongs to same tenant
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if current_user.role != UserRole.SUPER_ADMIN:
        if target_user.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete users from other tenants"
            )
        
        if target_user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete super admin users"
            )
    
    success = service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return SuccessResponse(
        success=True,
        message="User deleted successfully"
    )

@router.post("/{user_id}/activate", response_model=SuccessResponse)
async def activate_user(
    user_id: int,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Activate deactivated user
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    success = service.activate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return SuccessResponse(
        success=True,
        message="User activated successfully"
    )

@router.post("/{user_id}/deactivate", response_model=SuccessResponse)
async def deactivate_user(
    user_id: int,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Deactivate user (prevent login)
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    # Prevent self-deactivation
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    success = service.deactivate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return SuccessResponse(
        success=True,
        message="User deactivated successfully"
    )

@router.put("/{user_id}/role", response_model=User)
async def change_user_role(
    user_id: int,
    new_role: UserRole,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Change user's role
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Restrictions:**
    - Only Super Admin can assign/remove SUPER_ADMIN role
    - Only Super Admin can assign/remove CLINIC_ADMIN role
    - Cannot change own role
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    # Prevent self role change
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    # Role permission checks
    if new_role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can assign super admin role"
        )
    
    if new_role == UserRole.CLINIC_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can assign clinic admin role"
        )
    
    try:
        user = service.change_user_role(user_id, new_role)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{user_id}/permissions", response_model=User)
async def update_user_permissions(
    user_id: int,
    permissions: dict,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update user's granular permissions
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Example permissions:**
```json
    {
        "can_view_billing": true,
        "can_edit_patients": true,
        "can_delete_appointments": false,
        "can_export_data": true
    }
```
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    user = service.update_user_permissions(user_id, permissions)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/{user_id}/activity", response_model=dict)
async def get_user_activity(
    user_id: int,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    days: int = Query(30, ge=1, le=90)
):
    """
    Get user activity statistics
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Returns:**
    - Login history
    - Actions performed
    - Last activity timestamp
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    activity = service.get_user_activity(user_id, days=days)
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return activity

@router.post("/{user_id}/reset-password", response_model=SuccessResponse)
async def admin_reset_user_password(
    user_id: int,
    new_password: str = Query(..., min_length=8),
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Reset user's password (admin function)
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Use case:** When user forgets password and email recovery fails
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    # Validate target user
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if current_user.role != UserRole.SUPER_ADMIN:
        if target_user.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reset password for users from other tenants"
            )
        
        if target_user.role in [UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reset admin passwords"
            )
    
    success = service.admin_reset_password(user_id, new_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Password reset successfully. User should change it on next login."
    )

@router.post("/{user_id}/send-welcome-email", response_model=SuccessResponse)
async def send_welcome_email(
    user_id: int,
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Send welcome email to user
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Use case:** Resend welcome email if initial email was missed
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    success = service.send_welcome_email(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Welcome email sent successfully"
    )

@router.get("/search/email", response_model=User)
async def search_user_by_email(
    email: str = Query(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'),
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Search user by email
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    user = service.get_user_by_email(email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify tenant access
    if current_user.role != UserRole.SUPER_ADMIN:
        if user.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    return user

@router.get("/stats/summary", response_model=dict)
async def get_users_summary(
    current_user: UserModel = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get user statistics summary
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Returns:**
    - Total users
    - Active users
    - Users by role
    - Recent registrations
    """
    service = UserService(db, current_tenant.id, current_user.id)
    
    summary = service.get_users_summary()
    
    return summary