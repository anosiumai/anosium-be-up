# repositories/appointment.py
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime, date, time, timedelta

from models.appointment import Appointment, AppointmentStatus
from repositories.base import BaseRepository

class AppointmentRepository(BaseRepository[Appointment]):
    """Repository for Appointment operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Appointment, db, tenant_id, current_user_id)
    
    def get_by_appointment_code(self, appointment_code: str) -> Optional[Appointment]:
        """Get appointment by code"""
        query = self.db.query(Appointment).filter(
            Appointment.appointment_code == appointment_code
        )
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_details(self, appointment_id: int) -> Optional[Appointment]:
        """Get appointment with patient and doctor details"""
        query = self.db.query(Appointment).options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor).joinedload('user')
        )
        query = query.filter(Appointment.id == appointment_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_patient(
        self,
        patient_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Appointment]:
        """Get appointments for a patient"""
        query = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(Appointment.appointment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_doctor(
        self,
        doctor_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Appointment]:
        """Get appointments for a doctor"""
        query = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(Appointment.appointment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_date_range(
        self,
        from_date: date,
        to_date: date,
        doctor_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Appointment]:
        """Get appointments in date range"""
        query = self.db.query(Appointment).filter(
            and_(
                Appointment.appointment_date >= from_date,
                Appointment.appointment_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        
        if patient_id:
            query = query.filter(Appointment.patient_id == patient_id)
        
        return (
            query.order_by(Appointment.appointment_date, Appointment.appointment_time)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_today_appointments(
        self,
        doctor_id: Optional[int] = None
    ) -> List[Appointment]:
        """Get today's appointments"""
        today = date.today()
        
        query = self.db.query(Appointment).filter(
            Appointment.appointment_date == today
        )
        query = self._apply_tenant_filter(query)
        
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        
        return query.order_by(Appointment.appointment_time).all()
    
    def get_upcoming_appointments(
        self,
        days: int = 7,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Appointment]:
        """Get upcoming appointments"""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        query = self.db.query(Appointment).filter(
            and_(
                Appointment.appointment_date >= today,
                Appointment.appointment_date <= end_date,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED
                ])
            )
        )
        query = self._apply_tenant_filter(query)
        
        if patient_id:
            query = query.filter(Appointment.patient_id == patient_id)
        
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        
        return (
            query.order_by(Appointment.appointment_date, Appointment.appointment_time)
            .limit(limit)
            .all()
        )
    
    def check_conflict(
        self,
        doctor_id: int,
        appointment_date: date,
        appointment_time: time,
        duration_minutes: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if appointment time conflicts with existing appointments"""
        # Calculate time range
        from datetime import datetime as dt, timedelta
        
        start_datetime = dt.combine(appointment_date, appointment_time)
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        query = self.db.query(Appointment).filter(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW
                ])
            )
        )
        query = self._apply_tenant_filter(query)
        
        if exclude_id:
            query = query.filter(Appointment.id != exclude_id)
        
        appointments = query.all()
        
        # Check for time conflicts
        for apt in appointments:
            apt_start = dt.combine(apt.appointment_date, apt.appointment_time)
            apt_end = apt_start + timedelta(minutes=apt.duration_minutes)
            
            # Check if there's overlap
            if (start_datetime < apt_end and end_datetime > apt_start):
                return True
        
        return False
    
    def generate_appointment_code(self) -> str:
        """Generate unique appointment code"""
        query = self.db.query(func.count(Appointment.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        today = date.today()
        return f"APT-{today.strftime('%Y%m%d')}-{count + 1:04d}"
    
    def count_by_status(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, int]:
        """Count appointments by status"""
        query = self.db.query(
            Appointment.status,
            func.count(Appointment.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Appointment.appointment_date >= from_date)
        
        if to_date:
            query = query.filter(Appointment.appointment_date <= to_date)
        
        results = query.group_by(Appointment.status).all()
        
        return {status.value: count for status, count in results}
    
    def get_pending_reminders(self, hours_before: int = 24) -> List[Appointment]:
        """Get appointments that need reminders"""
        from datetime import datetime, timedelta
        
        reminder_time = datetime.utcnow() + timedelta(hours=hours_before)
        
        query = self.db.query(Appointment).filter(
            and_(
                Appointment.reminder_sent == False,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED
                ]),
                func.datetime(
                    Appointment.appointment_date,
                    Appointment.appointment_time
                ) <= reminder_time
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.all()