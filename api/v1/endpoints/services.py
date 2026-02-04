from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from api import deps
from schemas.service import (
    Service, ServiceCreate, ServiceUpdate,
    Package, PackageCreate
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.service_service import ServiceService
from models.user import User
from models.tenant import Tenant
from models.service import ServiceType

router = APIRouter()

# ========== SERVICES ==========

@router.post("", response_model=Service, status_code=status.HTTP_201_CREATED)
async def create_service(
    service_in: ServiceCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new service
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    try:
        service = service_svc.create_service(service_in)
        return service
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=PaginatedResponse[Service])
async def list_services(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    service_type: Optional[ServiceType] = None,
    department_id: Optional[int] = None,
    is_active: bool = True
):
    """
    Get list of services with filtering
    
    **Filters:**
    - service_type: Filter by service type
    - department_id: Filter by department
    - is_active: Filter active/inactive services
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    filters = {"is_active": is_active}
    if service_type:
        filters["service_type"] = service_type
    if department_id:
        filters["department_id"] = department_id
    
    result = service_svc.get_services(
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

@router.get("/{service_id}", response_model=Service)
async def get_service(
    service_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get service by ID
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    service = service_svc.get_service(service_id)
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return service

@router.put("/{service_id}", response_model=Service)
async def update_service(
    service_id: int,
    service_in: ServiceUpdate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update service
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    service = service_svc.update_service(service_id, service_in)
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return service

@router.delete("/{service_id}", response_model=SuccessResponse)
async def delete_service(
    service_id: int,
    soft_delete: bool = True,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete service (soft delete by default)
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    success = service_svc.delete_service(service_id, soft=soft_delete)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Service deleted successfully"
    )

# ========== PACKAGES ==========

@router.post("/packages", response_model=Package, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_in: PackageCreate,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new service package
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    try:
        package = service_svc.create_package(package_in)
        return package
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/packages", response_model=List[Package])
async def list_packages(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    is_active: bool = True
):
    """
    Get list of service packages
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    packages = service_svc.get_packages(filters={"is_active": is_active})
    return packages

@router.get("/packages/{package_id}", response_model=Package)
async def get_package(
    package_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get package by ID with included services
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    package = service_svc.get_package_with_services(package_id)
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    return package

@router.delete("/packages/{package_id}", response_model=SuccessResponse)
async def delete_package(
    package_id: int,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Delete package
    
    **Required Permissions:** Clinic Admin or Super Admin
    """
    service_svc = ServiceService(db, current_tenant.id, current_user.id)
    
    success = service_svc.delete_package(package_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
    
    return SuccessResponse(
        success=True,
        message="Package deleted successfully"
    )