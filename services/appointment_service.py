from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta

from repositories.appointment import AppointmentRepository
from repositories.doctor import DoctorRepository
from repositories.patient import PatientRepository
from schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentReschedule
from models.appointment import Appointment, AppointmentStatus
from services.base_service import BaseService

class AppointmentService(BaseService):
    """Appointment management service"""
    
    def __init__(
        self,
        db: Session,
        tenant_id: int,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, tenant_id, current_user_id)
        self.appointment_repo = AppointmentRepository(db, tenant_id, current_user_id)
        self.doctor_repo = DoctorRepository(db, tenant_id, current_user_id)
        self.patient_repo = PatientRepository(db, tenant_id, current_user_id)
    
    def create_appointment(self, appointment_in: AppointmentCreate) -> Appointment:
        """Create new appointment"""
        # Validate patient exists
        patient = self.patient_repo.get(appointment_in.patient_id)
        if not patient:
            raise ValueError("Patient not found")
        
        # Validate doctor exists and is available
        doctor = self.doctor_repo.get(appointment_in.doctor_id)
        if not doctor:
            raise ValueError("Doctor not found")
        
        if not doctor.is_available:
            raise ValueError("Doctor is not currently accepting appointments")
        
        # Check doctor availability for the date/time
        availability = self.doctor_repo.get_doctor_availability(
            appointment_in.doctor_id,
            appointment_in.appointment_date
        )
        
        if not availability.get('available'):
            raise ValueError(f"Doctor is not available on {appointment_in.appointment_date}")
        
        # Check for conflicts
        has_conflict = self.appointment_repo.check_conflict(
            appointment_in.doctor_id,
            appointment_in.appointment_date,
            appointment_in.appointment_time,
            appointment_in.duration_minutes
        )
        
        if has_conflict:
            raise ValueError("This time slot is already booked")
        
        # Generate appointment code
        appointment_code = self.appointment_repo.generate_appointment_code()
        
        # Create appointment
        appointment_data = appointment_in.dict()
        appointment_data['appointment_code'] = appointment_code
        appointment_data['status'] = AppointmentStatus.SCHEDULED
        
        appointment = self.appointment_repo.create(appointment_data)
        self.commit()
        
        # Schedule reminder (implement separately)
        # self._schedule_reminder(appointment)
        
        return appointment
    
    def get_appointment(self, appointment_id: int) -> Optional[Appointment]:
        """Get appointment by ID"""
        return self.appointment_repo.get(appointment_id)
    
    def get_appointment_with_details(self, appointment_id: int) -> Optional[Appointment]:
        """Get appointment with full details"""
        return self.appointment_repo.get_with_details(appointment_id)
    
    def get_appointments(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get list of appointments"""
        if from_date or to_date:
            from_date = from_date or date.today()
            to_date = to_date or (from_date + timedelta(days=30))
            
            appointments = self.appointment_repo.get_by_date_range(
                from_date,
                to_date,
                filters.get('doctor_id') if filters else None,
                filters.get('patient_id') if filters else None,
                skip,
                limit
            )
        else:
            appointments = self.appointment_repo.get_multi(skip, limit, filters)
        
        total = self.appointment_repo.count(filters)
        
        return {
            'items': appointments,
            'total': total
        }
    
    def update_appointment(
        self,
        appointment_id: int,
        appointment_in: AppointmentUpdate
    ) -> Optional[Appointment]:
        """Update appointment"""
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            return None
        
        update_data = appointment_in.dict(exclude_unset=True)
        
        # Check for conflicts if time is being changed
        if 'appointment_date' in update_data or 'appointment_time' in update_data:
            new_date = update_data.get('appointment_date', appointment.appointment_date)
            new_time = update_data.get('appointment_time', appointment.appointment_time)
            duration = update_data.get('duration_minutes', appointment.duration_minutes)
            
            has_conflict = self.appointment_repo.check_conflict(
                appointment.doctor_id,
                new_date,
                new_time,
                duration,
                exclude_id=appointment_id
            )
            
            if has_conflict:
                raise ValueError("This time slot is already booked")
        
        appointment = self.appointment_repo.update(appointment_id, update_data)
        self.commit()
        
        return appointment
    
    def reschedule_appointment(
        self,
        appointment_id: int,
        reschedule_data: AppointmentReschedule
    ) -> Optional[Appointment]:
        """Reschedule appointment to new date/time"""
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            return None
        
        # Check availability
        availability = self.doctor_repo.get_doctor_availability(
            appointment.doctor_id,
            reschedule_data.new_date
        )
        
        if not availability.get('available'):
            raise ValueError(f"Doctor is not available on {reschedule_data.new_date}")
        
        # Check for conflicts
        has_conflict = self.appointment_repo.check_conflict(
            appointment.doctor_id,
            reschedule_data.new_date,
            reschedule_data.new_time,
            appointment.duration_minutes,
            exclude_id=appointment_id
        )
        
        if has_conflict:
            raise ValueError("This time slot is already booked")
        
        # Update appointment
        update_data = {
            'appointment_date': reschedule_data.new_date,
            'appointment_time': reschedule_data.new_time,
            'status': AppointmentStatus.RESCHEDULED,
            'notes': f"{appointment.notes or ''}\nRescheduled: {reschedule_data.reason}"
        }
        
        appointment = self.appointment_repo.update(appointment_id, update_data)
        self.commit()
        
        return appointment
    
    def cancel_appointment(self, appointment_id: int, reason: str) -> bool:
        """Cancel appointment"""
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            return False
        
        update_data = {
            'status': AppointmentStatus.CANCELLED,
            'cancelled_at': datetime.utcnow(),
            'cancellation_reason': reason
        }
        
        self.appointment_repo.update(appointment_id, update_data)
        self.commit()
        
        return True
    
    def check_in_appointment(self, appointment_id: int) -> Optional[Appointment]:
        """Check in patient for appointment"""
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            return None
        
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise ValueError("Only scheduled appointments can be checked in")
        
        update_data = {
            'status': AppointmentStatus.CHECKED_IN,
            'checked_in_at': datetime.utcnow()
        }
        
        appointment = self.appointment_repo.update(appointment_id, update_data)
        self.commit()
        
        return appointment
    
    def complete_appointment(self, appointment_id: int) -> Optional[Appointment]:
        """Mark appointment as completed"""
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            return None
        
        update_data = {
            'status': AppointmentStatus.COMPLETED,
            'completed_at': datetime.utcnow()
        }
        
        appointment = self.appointment_repo.update(appointment_id, update_data)
        self.commit()
        
        return appointment
    
    def get_today_appointments(self, doctor_id: Optional[int] = None) -> List[Appointment]:
        """Get today's appointments"""
        return self.appointment_repo.get_today_appointments(doctor_id)
    
    def get_upcoming_appointments(
        self,
        days: int = 7,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None
    ) -> List[Appointment]:
        """Get upcoming appointments"""
        return self.appointment_repo.get_upcoming_appointments(days, patient_id, doctor_id)
    
    def get_doctor_availability(
        self,
        doctor_id: int,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get available time slots for a doctor"""
        doctor = self.doctor_repo.get(doctor_id)
        if not doctor:
            raise ValueError("Doctor not found")
        
        available_slots = []
        current_date = from_date
        
        while current_date <= to_date:
            # Get doctor's schedule for this day
            availability = self.doctor_repo.get_doctor_availability(doctor_id, current_date)
            
            if availability.get('available'):
                # Get existing appointments for this day
                existing_appointments = self.appointment_repo.get_by_date_range(
                    current_date,
                    current_date,
                    doctor_id=doctor_id
                )
                
                # Generate time slots
                start_time = datetime.strptime(availability['start_time'], '%H:%M').time()
                end_time = datetime.strptime(availability['end_time'], '%H:%M').time()
                slot_duration = doctor.average_consultation_time
                
                current_time = datetime.combine(current_date, start_time)
                end_datetime = datetime.combine(current_date, end_time)
                
                while current_time < end_datetime:
                    # Check if slot is available
                    slot_time = current_time.time()
                    is_booked = any(
                        apt.appointment_time == slot_time
                        for apt in existing_appointments
                        if apt.status not in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                    )
                    
                    if not is_booked:
                        available_slots.append({
                            'date': current_date,
                            'time': slot_time,
                            'duration_minutes': slot_duration,
                            'is_available': True,
                            'doctor_id': doctor_id,
                            'doctor_name': doctor.user.full_name
                        })
                    
                    current_time += timedelta(minutes=slot_duration)
            
            current_date += timedelta(days=1)
        
        return available_slots