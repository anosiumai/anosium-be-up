from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.department import (
    Department, DepartmentCreate, DepartmentUpdate, DepartmentWithDoctors
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.department_service import DepartmentService
from models.user import User
from models.tenant import Tenant

router = APIRouter()

@router.post("", response_model=Department, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_in: DepartmentCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new department
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    
    try:
        department = service.create_department(department_in)
        return department
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Department])
async def list_departments(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    is_active: bool = True
):
    """
    Get list of departments
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    
    result = service.get_departments(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters={"is_active": is_active}
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/{department_id}", response_model=DepartmentWithDoctors)
async def get_department(
    department_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get department with doctors list
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    department = service.get_department_with_doctors(department_id)
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return department

@router.put("/{department_id}", response_model=Department)
async def update_department(
    department_id: int,
    department_in: DepartmentUpdate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update department
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    
    department = service.update_department(department_id, department_in)
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return department

@router.delete("/{department_id}", response_model=SuccessResponse)
async def delete_department(
    department_id: int,
    soft_delete: bool = True,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete department (soft delete by default)
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    
    success = service.delete_department(department_id, soft=soft_delete)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Department deleted successfully"
    )

@router.post("/{department_id}/assign-head", response_model=Department)
async def assign_department_head(
    department_id: int,
    doctor_id: int,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Assign head doctor to department
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service = DepartmentService(db, current_tenant.id, current_user.id)
    
    try:
        department = service.assign_head_doctor(department_id, doctor_id)
        
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        return department
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )