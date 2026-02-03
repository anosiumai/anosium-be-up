from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta

from models.visit import Visit, VisitStatus
from repositories.base import BaseRepository

class VisitRepository(BaseRepository[Visit]):
    """Repository for Visit operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Visit, db, tenant_id, current_user_id)
    
    def get_by_visit_code(self, visit_code: str) -> Optional[Visit]:
        """Get visit by visit code"""
        query = self.db.query(Visit).filter(Visit.visit_code == visit_code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_details(self, visit_id: int) -> Optional[Visit]:
        """Get visit with patient, doctor, and related details"""
        query = self.db.query(Visit).options(
            joinedload(Visit.patient),
            joinedload(Visit.doctor).joinedload('user'),
            joinedload(Visit.appointment),
            joinedload(Visit.visit_services),
            joinedload(Visit.invoice)
        )
        query = query.filter(Visit.id == visit_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_patient(
        self,
        patient_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Visit]:
        """Get visits for a patient"""
        query = self.db.query(Visit).filter(Visit.patient_id == patient_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Visit.visit_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_doctor(
        self,
        doctor_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Visit]:
        """Get visits for a doctor"""
        query = self.db.query(Visit).filter(Visit.doctor_id == doctor_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Visit.visit_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_appointment(self, appointment_id: int) -> Optional[Visit]:
        """Get visit by appointment ID"""
        query = self.db.query(Visit).filter(Visit.appointment_id == appointment_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_patient_history(
        self,
        patient_id: int,
        limit: int = 10
    ) -> List[Visit]:
        """Get patient's visit history"""
        query = self.db.query(Visit).filter(
            and_(
                Visit.patient_id == patient_id,
                Visit.status == VisitStatus.COMPLETED
            )
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Visit.visit_date))
            .limit(limit)
            .all()
        )
    
    def get_by_date_range(
        self,
        from_date: datetime,
        to_date: datetime,
        doctor_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Visit]:
        """Get visits in date range"""
        query = self.db.query(Visit).filter(
            and_(
                Visit.visit_date >= from_date,
                Visit.visit_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        if doctor_id:
            query = query.filter(Visit.doctor_id == doctor_id)
        
        if patient_id:
            query = query.filter(Visit.patient_id == patient_id)
        
        return (
            query.order_by(desc(Visit.visit_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_today_visits(
        self,
        doctor_id: Optional[int] = None
    ) -> List[Visit]:
        """Get today's visits"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        query = self.db.query(Visit).filter(
            and_(
                Visit.visit_date >= today_start,
                Visit.visit_date < today_end
            )
        )
        query = self._apply_tenant_filter(query)
        
        if doctor_id:
            query = query.filter(Visit.doctor_id == doctor_id)
        
        return query.order_by(Visit.visit_date).all()
    
    def get_pending_visits(
        self,
        doctor_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Visit]:
        """Get pending/in-progress visits"""
        query = self.db.query(Visit).filter(
            Visit.status == VisitStatus.IN_PROGRESS
        )
        query = self._apply_tenant_filter(query)
        
        if doctor_id:
            query = query.filter(Visit.doctor_id == doctor_id)
        
        return query.order_by(Visit.visit_date).limit(limit).all()
    
    def get_follow_up_required(
        self,
        days_ahead: int = 30,
        limit: int = 100
    ) -> List[Visit]:
        """Get visits that require follow-up"""
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        
        query = self.db.query(Visit).filter(
            and_(
                Visit.follow_up_required == True,
                Visit.follow_up_date >= today,
                Visit.follow_up_date <= end_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(Visit.follow_up_date).limit(limit).all()
    
    def search_by_diagnosis(
        self,
        diagnosis_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Visit]:
        """Search visits by diagnosis"""
        query = self.db.query(Visit).filter(
            Visit.diagnosis.ilike(f"%{diagnosis_term}%")
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def generate_visit_code(self) -> str:
        """Generate unique visit code"""
        query = self.db.query(func.count(Visit.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        today = date.today()
        return f"VST-{today.strftime('%Y%m%d')}-{count + 1:04d}"
    
    def count_by_status(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Count visits by status"""
        query = self.db.query(
            Visit.status,
            func.count(Visit.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Visit.visit_date >= from_date)
        
        if to_date:
            query = query.filter(Visit.visit_date <= to_date)
        
        results = query.group_by(Visit.status).all()
        
        return {status.value: count for status, count in results}
    
    def get_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get visit statistics"""
        query = self.db.query(Visit)
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Visit.visit_date >= from_date)
        
        if to_date:
            query = query.filter(Visit.visit_date <= to_date)
        
        total_visits = query.count()
        completed_visits = query.filter(Visit.status == VisitStatus.COMPLETED).count()
        
        return {
            'total_visits': total_visits,
            'completed_visits': completed_visits,
            'in_progress': query.filter(Visit.status == VisitStatus.IN_PROGRESS).count(),
            'pending_payment': query.filter(Visit.status == VisitStatus.PENDING_PAYMENT).count(),
            'follow_ups_required': query.filter(Visit.follow_up_required == True).count()
        }