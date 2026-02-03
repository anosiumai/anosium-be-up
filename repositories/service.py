from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_

from models.service import Service, ServiceType, Package, PackageService
from repositories.base import BaseRepository

class ServiceRepository(BaseRepository[Service]):
    """Repository for Service operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Service, db, tenant_id, current_user_id)
    
    def get_by_code(self, code: str) -> Optional[Service]:
        """Get service by code"""
        query = self.db.query(Service).filter(Service.code == code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_type(
        self,
        service_type: ServiceType,
        skip: int = 0,
        limit: int = 100
    ) -> List[Service]:
        """Get services by type"""
        query = self.db.query(Service).filter(Service.service_type == service_type)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_department(
        self,
        department_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Service]:
        """Get services by department"""
        query = self.db.query(Service).filter(Service.department_id == department_id)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_active_services(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Service]:
        """Get all active services"""
        query = self.db.query(Service).filter(Service.is_active == True)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def search_services(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Service]:
        """Search services by name or code"""
        query = self.db.query(Service).filter(
            or_(
                Service.name.ilike(f"%{search_term}%"),
                Service.code.ilike(f"%{search_term}%"),
                Service.description.ilike(f"%{search_term}%")
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def check_code_exists(
        self,
        code: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if service code exists"""
        query = self.db.query(Service).filter(Service.code == code)
        query = self._apply_tenant_filter(query)
        
        if exclude_id:
            query = query.filter(Service.id != exclude_id)
        
        return query.first() is not None
    
    def count_by_type(self) -> Dict[str, int]:
        """Count services by type"""
        query = self.db.query(
            Service.service_type,
            func.count(Service.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(Service.service_type).all()
        
        return {stype.value: count for stype, count in results}
    
    def get_price_range(self) -> Dict[str, int]:
        """Get min and max service prices"""
        query = self.db.query(
            func.min(Service.base_price).label('min_price'),
            func.max(Service.base_price).label('max_price'),
            func.avg(Service.base_price).label('avg_price')
        )
        query = self._apply_tenant_filter(query)
        
        result = query.first()
        
        return {
            'min_price': result.min_price or 0,
            'max_price': result.max_price or 0,
            'avg_price': int(result.avg_price or 0)
        }

class PackageRepository(BaseRepository[Package]):
    """Repository for Package operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Package, db, tenant_id, current_user_id)
    
    def get_by_code(self, code: str) -> Optional[Package]:
        """Get package by code"""
        query = self.db.query(Package).filter(Package.code == code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_services(self, package_id: int) -> Optional[Package]:
        """Get package with included services"""
        query = self.db.query(Package).options(
            joinedload(Package.package_services).joinedload(PackageService.service)
        )
        query = query.filter(Package.id == package_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_active_packages(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Package]:
        """Get all active packages"""
        query = self.db.query(Package).filter(Package.is_active == True)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def check_code_exists(
        self,
        code: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if package code exists"""
        query = self.db.query(Package).filter(Package.code == code)
        query = self._apply_tenant_filter(query)
        
        if exclude_id:
            query = query.filter(Package.id != exclude_id)
        
        return query.first() is not None