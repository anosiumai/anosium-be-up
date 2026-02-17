from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from models.department import Department
from repositories.base import BaseRepository

class DepartmentRepository(BaseRepository[Department]):
    """Repository for Department operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, Department, tenant_id, current_user_id)
    
    def get_by_code(self, code: str) -> Optional[Department]:
        """Get department by code"""
        query = self.db.query(Department).filter(Department.code == code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_doctors(self, department_id: int) -> Optional[Department]:
        """Get department with doctors"""
        query = self.db.query(Department).options(
            joinedload(Department.doctors)
        )
        query = query.filter(Department.id == department_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_head_doctor(self, department_id: int) -> Optional[Department]:
        """Get department with head doctor"""
        query = self.db.query(Department).options(
            joinedload(Department.head_doctor)
        )
        query = query.filter(Department.id == department_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def check_code_exists(
        self,
        code: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if department code exists"""
        query = self.db.query(Department).filter(Department.code == code)
        query = self._apply_tenant_filter(query)
        
        if exclude_id:
            query = query.filter(Department.id != exclude_id)
        
        return query.first() is not None
    
    def get_active_departments(self) -> List[Department]:
        """Get all active departments"""
        query = self.db.query(Department).filter(Department.is_active == True)
        query = self._apply_tenant_filter(query)
        return query.all()