from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime, date, time

from models.doctor import Doctor
from repositories.base import BaseRepository

class DoctorRepository(BaseRepository[Doctor]):
    """Repository for Doctor operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Doctor, db, tenant_id, current_user_id)
    
    def get_by_doctor_code(self, doctor_code: str) -> Optional[Doctor]:
        """Get doctor by doctor code"""
        query = self.db.query(Doctor).filter(Doctor.doctor_code == doctor_code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_user_id(self, user_id: int) -> Optional[Doctor]:
        """Get doctor by user ID"""
        query = self.db.query(Doctor).filter(Doctor.user_id == user_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_user(self, doctor_id: int) -> Optional[Doctor]:
        """Get doctor with user information"""
        query = self.db.query(Doctor).options(joinedload(Doctor.user))
        query = query.filter(Doctor.id == doctor_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_department(
        self,
        department_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Doctor]:
        """Get doctors by department"""
        query = self.db.query(Doctor).filter(Doctor.department_id == department_id)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_specialization(
        self,
        specialization: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Doctor]:
        """Get doctors by specialization"""
        query = self.db.query(Doctor).filter(
            Doctor.specialization.ilike(f"%{specialization}%")
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_available_doctors(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Doctor]:
        """Get available doctors"""
        query = self.db.query(Doctor).filter(
            and_(
                Doctor.is_available == True,
                Doctor.is_active == True
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def search_doctors(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Doctor]:
        """Search doctors by name, specialization, or code"""
        from models.user import User
        
        query = self.db.query(Doctor).join(User).filter(
            or_(
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%"),
                Doctor.specialization.ilike(f"%{search_term}%"),
                Doctor.doctor_code.ilike(f"%{search_term}%")
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def generate_doctor_code(self) -> str:
        """Generate unique doctor code"""
        query = self.db.query(func.count(Doctor.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        return f"DOC-{count + 1:05d}"
    
    def get_doctor_availability(
        self,
        doctor_id: int,
        check_date: date
    ) -> Dict[str, Any]:
        """Get doctor's availability for a specific date"""
        doctor = self.get(doctor_id)
        if not doctor or not doctor.is_available:
            return {"available": False}
        
        day_name = check_date.strftime('%A').lower()
        schedule = doctor.availability_schedule or {}
        
        day_schedule = schedule.get(day_name, {})
        
        if not day_schedule or not day_schedule.get('is_available', False):
            return {"available": False}
        
        return {
            "available": True,
            "start_time": day_schedule.get('start_time'),
            "end_time": day_schedule.get('end_time'),
            "slots": day_schedule.get('slots'),
            "break_start": day_schedule.get('break_start'),
            "break_end": day_schedule.get('break_end')
        }
    
    def count_by_specialization(self) -> Dict[str, int]:
        """Count doctors by specialization"""
        query = self.db.query(
            Doctor.specialization,
            func.count(Doctor.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(Doctor.specialization).all()
        
        return {spec: count for spec, count in results}