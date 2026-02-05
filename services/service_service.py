"""
Service Management
Handles medical services, packages, and pricing
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models.service import Service, Package, PackageService, ServiceType
from models.department import Department
from repositories.service import ServiceRepository, PackageRepository
from schemas.service import (
    ServiceCreate, ServiceUpdate, Service as ServiceSchema,
    PackageCreate, PackageUpdate, Package as PackageSchema,
    PackageWithServices
)
from services.base_service import BaseService


class ServiceService(BaseService):
    """Service for medical services operations"""
    
    def __init__(self, db: Session, tenant_id: int, current_user_id: int):
        super().__init__(db, tenant_id, current_user_id)
        self.service_repo = ServiceRepository(db, tenant_id, current_user_id)
    
    # ============================================================================
    # SERVICE CRUD OPERATIONS
    # ============================================================================
    
    def create_service(self, service_in: ServiceCreate) -> ServiceSchema:
        """
        Create new medical service
        
        Args:
            service_in: Service creation data
            
        Returns:
            Created service
            
        Raises:
            ValueError: If service code already exists or department not found
        """
        # Check if code already exists
        if self.service_repo.check_code_exists(service_in.code.upper()):
            raise ValueError(f"Service code '{service_in.code}' already exists")
        
        # Validate department if provided
        if service_in.department_id:
            department = (
                self.db.query(Department)
                .filter(
                    and_(
                        Department.id == service_in.department_id,
                        Department.tenant_id == self.tenant_id,
                        Department.is_active == True
                    )
                )
                .first()
            )
            
            if not department:
                raise ValueError("Department not found or inactive")
        
        # Create service
        service = Service(
            tenant_id=self.tenant_id,
            name=service_in.name,
            code=service_in.code.upper(),
            description=service_in.description,
            service_type=service_in.service_type,
            department_id=service_in.department_id,
            base_price=service_in.base_price,
            tax_percentage=service_in.tax_percentage,
            estimated_duration_minutes=service_in.estimated_duration_minutes,
            is_active=True
        )
        
        self.db.add(service)
        self.commit()
        self.refresh(service)
        
        return ServiceSchema.from_orm(service)
    
    def get_service(self, service_id: int) -> Optional[ServiceSchema]:
        """
        Get service by ID
        
        Args:
            service_id: Service ID
            
        Returns:
            Service or None if not found
        """
        service = self.service_repo.get(service_id)
        
        if service:
            return ServiceSchema.from_orm(service)
        
        return None
    
    def get_services(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get list of services with filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter criteria
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(Service).filter(Service.tenant_id == self.tenant_id)
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                query = query.filter(Service.is_active == filters['is_active'])
            
            if 'service_type' in filters:
                query = query.filter(Service.service_type == filters['service_type'])
            
            if 'department_id' in filters:
                query = query.filter(Service.department_id == filters['department_id'])
            
            if 'search' in filters:
                search_term = filters['search']
                query = query.filter(
                    or_(
                        Service.name.ilike(f"%{search_term}%"),
                        Service.code.ilike(f"%{search_term}%"),
                        Service.description.ilike(f"%{search_term}%")
                    )
                )
            
            if 'min_price' in filters:
                query = query.filter(Service.base_price >= filters['min_price'])
            
            if 'max_price' in filters:
                query = query.filter(Service.base_price <= filters['max_price'])
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        services = query.order_by(Service.name).offset(skip).limit(limit).all()
        
        return {
            'items': [ServiceSchema.from_orm(service) for service in services],
            'total': total
        }
    
    def update_service(
        self,
        service_id: int,
        service_in: ServiceUpdate
    ) -> Optional[ServiceSchema]:
        """
        Update service
        
        Args:
            service_id: Service ID
            service_in: Update data
            
        Returns:
            Updated service or None if not found
            
        Raises:
            ValueError: If code already exists or department not found
        """
        service = self.service_repo.get(service_id)
        
        if not service:
            return None
        
        # Check if code is being changed and already exists
        if service_in.code and service_in.code != service.code:
            if self.service_repo.check_code_exists(
                service_in.code.upper(), 
                exclude_id=service_id
            ):
                raise ValueError(f"Service code '{service_in.code}' already exists")
        
        # Validate department if being changed
        if service_in.department_id is not None:
            if service_in.department_id:  # Not setting to None
                department = (
                    self.db.query(Department)
                    .filter(
                        and_(
                            Department.id == service_in.department_id,
                            Department.tenant_id == self.tenant_id,
                            Department.is_active == True
                        )
                    )
                    .first()
                )
                
                if not department:
                    raise ValueError("Department not found or inactive")
        
        # Update fields
        update_data = service_in.dict(exclude_unset=True)
        
        # Uppercase code if present
        if 'code' in update_data:
            update_data['code'] = update_data['code'].upper()
        
        for field, value in update_data.items():
            setattr(service, field, value)
        
        self.commit()
        self.refresh(service)
        
        return ServiceSchema.from_orm(service)
    
    def delete_service(self, service_id: int, soft: bool = True) -> bool:
        """
        Delete service
        
        Args:
            service_id: Service ID
            soft: If True, perform soft delete (set is_active=False)
            
        Returns:
            True if deleted successfully, False if not found
            
        Raises:
            ValueError: If service is used in packages or visits
        """
        service = self.service_repo.get(service_id)
        
        if not service:
            return False
        
        if soft:
            # Soft delete - mark as inactive
            service.is_active = False
            self.commit()
        else:
            # Hard delete - check for dependencies
            # Check if used in packages
            package_count = (
                self.db.query(func.count(PackageService.id))
                .filter(PackageService.service_id == service_id)
                .scalar() or 0
            )
            
            if package_count > 0:
                raise ValueError(
                    f"Cannot delete service that is part of {package_count} packages. "
                    "Use soft delete instead."
                )
            
            # Check if used in visits (via visit_services)
            # This would require the VisitService model
            # For now, we'll just do soft delete to be safe
            
            self.db.delete(service)
            self.commit()
        
        return True
    
    # ============================================================================
    # SERVICE SEARCH AND FILTERING
    # ============================================================================
    
    def search_services(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search services by name, code, or description
        
        Args:
            search_term: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with items and total count
        """
        services = self.service_repo.search_services(
            search_term=search_term,
            skip=skip,
            limit=limit
        )
        
        # Get total count
        query = self.db.query(Service).filter(
            and_(
                Service.tenant_id == self.tenant_id,
                or_(
                    Service.name.ilike(f"%{search_term}%"),
                    Service.code.ilike(f"%{search_term}%"),
                    Service.description.ilike(f"%{search_term}%")
                )
            )
        )
        
        total = query.count()
        
        return {
            'items': [ServiceSchema.from_orm(service) for service in services],
            'total': total
        }
    
    def get_services_by_type(
        self,
        service_type: ServiceType,
        skip: int = 0,
        limit: int = 100
    ) -> List[ServiceSchema]:
        """
        Get services by type
        
        Args:
            service_type: Service type to filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of services
        """
        services = self.service_repo.get_by_type(
            service_type=service_type,
            skip=skip,
            limit=limit
        )
        
        return [ServiceSchema.from_orm(service) for service in services]
    
    def get_services_by_department(
        self,
        department_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[ServiceSchema]:
        """
        Get services by department
        
        Args:
            department_id: Department ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of services
        """
        services = self.service_repo.get_by_department(
            department_id=department_id,
            skip=skip,
            limit=limit
        )
        
        return [ServiceSchema.from_orm(service) for service in services]
    
    def get_service_by_code(self, code: str) -> Optional[ServiceSchema]:
        """
        Get service by code
        
        Args:
            code: Service code
            
        Returns:
            Service or None if not found
        """
        service = self.service_repo.get_by_code(code.upper())
        
        if service:
            return ServiceSchema.from_orm(service)
        
        return None
    
    # ============================================================================
    # SERVICE STATISTICS
    # ============================================================================
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """
        Get service statistics summary
        
        Returns:
            Statistics dictionary
        """
        # Total services
        total_services = (
            self.db.query(func.count(Service.id))
            .filter(Service.tenant_id == self.tenant_id)
            .scalar() or 0
        )
        
        # Active services
        active_services = (
            self.db.query(func.count(Service.id))
            .filter(
                and_(
                    Service.tenant_id == self.tenant_id,
                    Service.is_active == True
                )
            )
            .scalar() or 0
        )
        
        # Services by type
        services_by_type = (
            self.db.query(
                Service.service_type,
                func.count(Service.id).label('count')
            )
            .filter(
                and_(
                    Service.tenant_id == self.tenant_id,
                    Service.is_active == True
                )
            )
            .group_by(Service.service_type)
            .all()
        )
        
        # Price range
        price_stats = (
            self.db.query(
                func.min(Service.base_price).label('min_price'),
                func.max(Service.base_price).label('max_price'),
                func.avg(Service.base_price).label('avg_price')
            )
            .filter(
                and_(
                    Service.tenant_id == self.tenant_id,
                    Service.is_active == True
                )
            )
            .first()
        )
        
        return {
            'total_services': total_services,
            'active_services': active_services,
            'inactive_services': total_services - active_services,
            'by_type': {
                str(service_type): count 
                for service_type, count in services_by_type
            },
            'price_range': {
                'min': price_stats.min_price or 0,
                'max': price_stats.max_price or 0,
                'average': round(price_stats.avg_price or 0, 2)
            }
        }
    
    # ============================================================================
    # SERVICE ACTIVATION
    # ============================================================================
    
    def activate_service(self, service_id: int) -> Optional[ServiceSchema]:
        """
        Activate service
        
        Args:
            service_id: Service ID
            
        Returns:
            Updated service or None if not found
        """
        service = self.service_repo.get(service_id)
        
        if not service:
            return None
        
        service.is_active = True
        
        self.commit()
        self.refresh(service)
        
        return ServiceSchema.from_orm(service)
    
    def deactivate_service(self, service_id: int) -> Optional[ServiceSchema]:
        """
        Deactivate service
        
        Args:
            service_id: Service ID
            
        Returns:
            Updated service or None if not found
        """
        service = self.service_repo.get(service_id)
        
        if not service:
            return None
        
        service.is_active = False
        
        self.commit()
        self.refresh(service)
        
        return ServiceSchema.from_orm(service)


class PackageService(BaseService):
    """Service for service packages operations"""
    
    def __init__(self, db: Session, tenant_id: int, current_user_id: int):
        super().__init__(db, tenant_id, current_user_id)
        self.package_repo = PackageRepository(db, tenant_id, current_user_id)
        self.service_repo = ServiceRepository(db, tenant_id, current_user_id)
    
    # ============================================================================
    # PACKAGE CRUD OPERATIONS
    # ============================================================================
    
    def create_package(self, package_in: PackageCreate) -> PackageSchema:
        """
        Create new service package
        
        Args:
            package_in: Package creation data
            
        Returns:
            Created package
            
        Raises:
            ValueError: If package code already exists or services not found
        """
        # Check if code already exists
        if self.package_repo.check_code_exists(package_in.code.upper()):
            raise ValueError(f"Package code '{package_in.code}' already exists")
        
        # Validate all services exist
        if package_in.service_ids:
            for service_id in package_in.service_ids:
                service = self.service_repo.get(service_id)
                if not service:
                    raise ValueError(f"Service with id {service_id} not found")
                if not service.is_active:
                    raise ValueError(f"Service '{service.name}' is not active")
        
        # Calculate package price if not provided
        package_price = package_in.package_price
        if package_price is None and package_in.service_ids:
            # Sum up service prices
            total_price = sum(
                self.service_repo.get(sid).base_price 
                for sid in package_in.service_ids
            )
            # Apply discount
            discount = package_in.discount_percentage or 0
            package_price = total_price - (total_price * discount // 100)
        
        # Create package
        package = Package(
            tenant_id=self.tenant_id,
            name=package_in.name,
            code=package_in.code.upper(),
            description=package_in.description,
            package_price=package_price,
            discount_percentage=package_in.discount_percentage,
            validity_days=package_in.validity_days,
            is_active=True
        )
        
        self.db.add(package)
        self.db.flush()  # Get package.id
        
        # Add services to package
        if package_in.service_ids:
            for service_id in package_in.service_ids:
                package_service = PackageService(
                    package_id=package.id,
                    service_id=service_id
                )
                self.db.add(package_service)
        
        self.commit()
        self.refresh(package)
        
        return PackageSchema.from_orm(package)
    
    def get_package(self, package_id: int) -> Optional[PackageSchema]:
        """
        Get package by ID
        
        Args:
            package_id: Package ID
            
        Returns:
            Package or None if not found
        """
        package = self.package_repo.get(package_id)
        
        if package:
            return PackageSchema.from_orm(package)
        
        return None
    
    def get_package_with_services(
        self,
        package_id: int
    ) -> Optional[PackageWithServices]:
        """
        Get package with services
        
        Args:
            package_id: Package ID
            
        Returns:
            Package with services or None if not found
        """
        package = self.package_repo.get_with_services(package_id)
        
        if not package:
            return None
        
        # Build response with services
        package_dict = PackageSchema.from_orm(package).dict()
        package_dict['services'] = [
            {
                'id': ps.service.id,
                'name': ps.service.name,
                'code': ps.service.code,
                'base_price': ps.service.base_price,
                'service_type': ps.service.service_type
            }
            for ps in package.package_services
        ]
        
        # Calculate savings
        total_individual = sum(
            ps.service.base_price for ps in package.package_services
        )
        savings = total_individual - package.package_price
        package_dict['savings'] = savings
        package_dict['total_individual_price'] = total_individual
        
        return PackageWithServices(**package_dict)
    
    def get_packages(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get list of packages with filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter criteria
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(Package).filter(Package.tenant_id == self.tenant_id)
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                query = query.filter(Package.is_active == filters['is_active'])
            
            if 'search' in filters:
                search_term = filters['search']
                query = query.filter(
                    or_(
                        Package.name.ilike(f"%{search_term}%"),
                        Package.code.ilike(f"%{search_term}%"),
                        Package.description.ilike(f"%{search_term}%")
                    )
                )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        packages = query.order_by(Package.name).offset(skip).limit(limit).all()
        
        return {
            'items': [PackageSchema.from_orm(pkg) for pkg in packages],
            'total': total
        }
    
    def update_package(
        self,
        package_id: int,
        package_in: PackageUpdate
    ) -> Optional[PackageSchema]:
        """
        Update package
        
        Args:
            package_id: Package ID
            package_in: Update data
            
        Returns:
            Updated package or None if not found
            
        Raises:
            ValueError: If code already exists or services not found
        """
        package = self.package_repo.get(package_id)
        
        if not package:
            return None
        
        # Check if code is being changed and already exists
        if package_in.code and package_in.code != package.code:
            if self.package_repo.check_code_exists(
                package_in.code.upper(), 
                exclude_id=package_id
            ):
                raise ValueError(f"Package code '{package_in.code}' already exists")
        
        # Update fields
        update_data = package_in.dict(exclude_unset=True, exclude={'service_ids'})
        
        # Uppercase code if present
        if 'code' in update_data:
            update_data['code'] = update_data['code'].upper()
        
        for field, value in update_data.items():
            setattr(package, field, value)
        
        # Update services if provided
        if package_in.service_ids is not None:
            # Validate services
            for service_id in package_in.service_ids:
                service = self.service_repo.get(service_id)
                if not service:
                    raise ValueError(f"Service with id {service_id} not found")
                if not service.is_active:
                    raise ValueError(f"Service '{service.name}' is not active")
            
            # Remove old services
            self.db.query(PackageService).filter(
                PackageService.package_id == package_id
            ).delete()
            
            # Add new services
            for service_id in package_in.service_ids:
                package_service = PackageService(
                    package_id=package.id,
                    service_id=service_id
                )
                self.db.add(package_service)
        
        self.commit()
        self.refresh(package)
        
        return PackageSchema.from_orm(package)
    
    def delete_package(self, package_id: int, soft: bool = True) -> bool:
        """
        Delete package
        
        Args:
            package_id: Package ID
            soft: If True, perform soft delete (set is_active=False)
            
        Returns:
            True if deleted successfully, False if not found
        """
        package = self.package_repo.get(package_id)
        
        if not package:
            return False
        
        if soft:
            # Soft delete - mark as inactive
            package.is_active = False
            self.commit()
        else:
            # Hard delete - remove services first
            self.db.query(PackageService).filter(
                PackageService.package_id == package_id
            ).delete()
            
            self.db.delete(package)
            self.commit()
        
        return True
    
    # ============================================================================
    # PACKAGE SERVICES MANAGEMENT
    # ============================================================================
    
    def add_service_to_package(
        self,
        package_id: int,
        service_id: int
    ) -> Optional[PackageWithServices]:
        """
        Add service to package
        
        Args:
            package_id: Package ID
            service_id: Service ID
            
        Returns:
            Updated package with services or None if not found
            
        Raises:
            ValueError: If service not found or already in package
        """
        package = self.package_repo.get(package_id)
        
        if not package:
            return None
        
        # Validate service
        service = self.service_repo.get(service_id)
        if not service:
            raise ValueError(f"Service with id {service_id} not found")
        if not service.is_active:
            raise ValueError(f"Service '{service.name}' is not active")
        
        # Check if already in package
        existing = (
            self.db.query(PackageService)
            .filter(
                and_(
                    PackageService.package_id == package_id,
                    PackageService.service_id == service_id
                )
            )
            .first()
        )
        
        if existing:
            raise ValueError("Service is already in this package")
        
        # Add service to package
        package_service = PackageService(
            package_id=package_id,
            service_id=service_id
        )
        self.db.add(package_service)
        
        self.commit()
        
        return self.get_package_with_services(package_id)
    
    def remove_service_from_package(
        self,
        package_id: int,
        service_id: int
    ) -> Optional[PackageWithServices]:
        """
        Remove service from package
        
        Args:
            package_id: Package ID
            service_id: Service ID
            
        Returns:
            Updated package with services or None if not found
        """
        package = self.package_repo.get(package_id)
        
        if not package:
            return None
        
        # Remove service from package
        self.db.query(PackageService).filter(
            and_(
                PackageService.package_id == package_id,
                PackageService.service_id == service_id
            )
        ).delete()
        
        self.commit()
        
        return self.get_package_with_services(package_id)


# Alias for backward compatibility
class ServiceManagementService(ServiceService):
    """
    Alias for ServiceService to maintain backward compatibility
    """
    pass