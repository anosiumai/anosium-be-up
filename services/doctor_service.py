"""
Doctor Service
Handles all doctor-related operations including profile management, scheduling, and statistics
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from datetime import datetime, date, time, timedelta

from models.doctor import Doctor
from models.user import User, UserRole
from models.appointment import Appointment, AppointmentStatus
from models.visit import Visit
from models.billing import Invoice
from models.department import Department
from repositories.doctor import DoctorRepository
from schemas.doctor import (
    DoctorCreate, DoctorUpdate, Doctor as DoctorSchema,
    DoctorWithSchedule, DoctorAvailability, DoctorStats
)


class DoctorService:
    """Service for doctor operations"""
    
    def __init__(self, db: Session, tenant_id: int, current_user_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
        self.doctor_repo = DoctorRepository(db, tenant_id, current_user_id)
    
    # ============================================================================
    # CRUD OPERATIONS
    # ============================================================================
    
    def create_doctor(self, doctor_in: DoctorCreate) -> DoctorSchema:
        """
        Create new doctor profile
        
        Args:
            doctor_in: Doctor creation data
            
        Returns:
            Created doctor profile
            
        Raises:
            ValueError: If user doesn't exist, already has doctor profile, 
                       or user role is not DOCTOR
        """
        # Validate user exists and belongs to tenant
        user = (
            self.db.query(User)
            .filter(
                and_(
                    User.id == doctor_in.user_id,
                    User.tenant_id == self.tenant_id
                )
            )
            .first()
        )
        
        if not user:
            raise ValueError("User not found or doesn't belong to this tenant")
        
        # Check if user already has a doctor profile
        existing_doctor = self.doctor_repo.get_by_user_id(doctor_in.user_id)
        if existing_doctor:
            raise ValueError("User already has a doctor profile")
        
        # Validate user has DOCTOR role
        if user.role != UserRole.DOCTOR:
            raise ValueError("User must have DOCTOR role")
        
        # Validate department if provided
        if doctor_in.department_id:
            department = (
                self.db.query(Department)
                .filter(
                    and_(
                        Department.id == doctor_in.department_id,
                        Department.tenant_id == self.tenant_id
                    )
                )
                .first()
            )
            if not department:
                raise ValueError("Department not found")
        
        # Generate doctor code
        doctor_code = self.doctor_repo.generate_doctor_code()
        
        # Prepare availability schedule
        availability_schedule = doctor_in.availability_schedule or self._get_default_schedule()
        
        # Create doctor
        doctor = Doctor(
            tenant_id=self.tenant_id,
            user_id=doctor_in.user_id,
            department_id=doctor_in.department_id,
            doctor_code=doctor_code,
            specialization=doctor_in.specialization,
            qualification=doctor_in.qualification,
            license_number=doctor_in.license_number,
            experience_years=doctor_in.experience_years,
            consultation_fee=doctor_in.consultation_fee,
            average_consultation_time=doctor_in.average_consultation_time,
            availability_schedule=availability_schedule,
            is_available=True,
            is_active=True,
            joined_date=doctor_in.joined_date or date.today(),
            bio=doctor_in.bio
        )
        
        self.db.add(doctor)
        self.db.commit()
        self.db.refresh(doctor)
        
        return DoctorSchema.from_orm(doctor)
    
    def get_doctor(self, doctor_id: int) -> Optional[DoctorSchema]:
        """
        Get doctor by ID
        
        Args:
            doctor_id: Doctor ID
            
        Returns:
            Doctor profile or None if not found
        """
        doctor = self.doctor_repo.get_with_user(doctor_id)
        
        if doctor:
            return DoctorSchema.from_orm(doctor)
        
        return None
    
    def get_doctors(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get list of doctors with filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter criteria
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(Doctor)
        
        # Apply tenant filter
        query = query.filter(Doctor.tenant_id == self.tenant_id)
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                query = query.filter(Doctor.is_active == filters['is_active'])
            
            if 'is_available' in filters:
                query = query.filter(Doctor.is_available == filters['is_available'])
            
            if 'department_id' in filters:
                query = query.filter(Doctor.department_id == filters['department_id'])
            
            if 'specialization' in filters:
                query = query.filter(
                    Doctor.specialization.ilike(f"%{filters['specialization']}%")
                )
            
            if 'search' in filters:
                search_term = filters['search']
                query = query.join(User).filter(
                    or_(
                        User.first_name.ilike(f"%{search_term}%"),
                        User.last_name.ilike(f"%{search_term}%"),
                        Doctor.specialization.ilike(f"%{search_term}%"),
                        Doctor.doctor_code.ilike(f"%{search_term}%")
                    )
                )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        doctors = query.offset(skip).limit(limit).all()
        
        return {
            'items': [DoctorSchema.from_orm(doc) for doc in doctors],
            'total': total
        }
    
    def update_doctor(
        self,
        doctor_id: int,
        doctor_in: DoctorUpdate
    ) -> Optional[DoctorSchema]:
        """
        Update doctor profile
        
        Args:
            doctor_id: Doctor ID
            doctor_in: Update data
            
        Returns:
            Updated doctor profile or None if not found
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return None
        
        # Validate department if being updated
        if doctor_in.department_id is not None:
            department = (
                self.db.query(Department)
                .filter(
                    and_(
                        Department.id == doctor_in.department_id,
                        Department.tenant_id == self.tenant_id
                    )
                )
                .first()
            )
            if not department:
                raise ValueError("Department not found")
        
        # Update fields
        update_data = doctor_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(doctor, field, value)
        
        self.db.commit()
        self.db.refresh(doctor)
        
        return DoctorSchema.from_orm(doctor)
    
    def delete_doctor(self, doctor_id: int, soft: bool = True) -> bool:
        """
        Delete doctor profile
        
        Args:
            doctor_id: Doctor ID
            soft: If True, perform soft delete (set is_active=False)
            
        Returns:
            True if deleted successfully, False if not found
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return False
        
        if soft:
            # Soft delete - mark as inactive
            doctor.is_active = False
            doctor.is_available = False
            self.db.commit()
        else:
            # Hard delete - check for dependencies
            has_appointments = (
                self.db.query(Appointment)
                .filter(Appointment.doctor_id == doctor_id)
                .first()
            ) is not None
            
            if has_appointments:
                raise ValueError(
                    "Cannot delete doctor with existing appointments. Use soft delete instead."
                )
            
            self.db.delete(doctor)
            self.db.commit()
        
        return True
    
    # ============================================================================
    # AVAILABILITY MANAGEMENT
    # ============================================================================
    
    def update_availability(
        self,
        doctor_id: int,
        availability: List[DoctorAvailability]
    ) -> Optional[DoctorSchema]:
        """
        Update doctor's weekly availability schedule
        
        Args:
            doctor_id: Doctor ID
            availability: List of daily availability schedules
            
        Returns:
            Updated doctor profile or None if not found
            
        Raises:
            ValueError: If availability data is invalid
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return None
        
        # Convert list to schedule dictionary
        schedule = {}
        for day_avail in availability:
            day = day_avail.day.lower()
            
            # Validate time ranges
            if day_avail.is_available:
                if not day_avail.start_time or not day_avail.end_time:
                    raise ValueError(
                        f"Start time and end time required for available day: {day}"
                    )
                
                if day_avail.start_time >= day_avail.end_time:
                    raise ValueError(
                        f"Start time must be before end time for {day}"
                    )
                
                # Validate break times if provided
                if day_avail.break_start and day_avail.break_end:
                    if day_avail.break_start >= day_avail.break_end:
                        raise ValueError(
                            f"Break start time must be before break end time for {day}"
                        )
                    
                    if (day_avail.break_start < day_avail.start_time or 
                        day_avail.break_end > day_avail.end_time):
                        raise ValueError(
                            f"Break times must be within working hours for {day}"
                        )
                
                # Calculate slots if not provided
                if not day_avail.slots:
                    working_minutes = self._calculate_working_minutes(
                        day_avail.start_time,
                        day_avail.end_time,
                        day_avail.break_start,
                        day_avail.break_end
                    )
                    day_avail.slots = working_minutes // doctor.average_consultation_time
            
            schedule[day] = {
                'is_available': day_avail.is_available,
                'start_time': day_avail.start_time.isoformat() if day_avail.start_time else None,
                'end_time': day_avail.end_time.isoformat() if day_avail.end_time else None,
                'slots': day_avail.slots,
                'break_start': day_avail.break_start.isoformat() if day_avail.break_start else None,
                'break_end': day_avail.break_end.isoformat() if day_avail.break_end else None
            }
        
        # Update schedule
        doctor.availability_schedule = schedule
        
        self.db.commit()
        self.db.refresh(doctor)
        
        return DoctorSchema.from_orm(doctor)
    
    def toggle_availability(self, doctor_id: int) -> Optional[DoctorSchema]:
        """
        Toggle doctor's overall availability status
        
        Args:
            doctor_id: Doctor ID
            
        Returns:
            Updated doctor profile or None if not found
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return None
        
        doctor.is_available = not doctor.is_available
        
        self.db.commit()
        self.db.refresh(doctor)
        
        return DoctorSchema.from_orm(doctor)
    
    def get_doctor_with_schedule(self, doctor_id: int) -> Optional[DoctorWithSchedule]:
        """
        Get doctor profile with parsed weekly schedule
        
        Args:
            doctor_id: Doctor ID
            
        Returns:
            Doctor with schedule or None if not found
        """
        doctor = self.doctor_repo.get_with_user(doctor_id)
        
        if not doctor:
            return None
        
        # Parse schedule
        weekly_schedule = self._parse_schedule_to_list(doctor.availability_schedule)
        
        # Create response with schedule
        doctor_dict = DoctorSchema.from_orm(doctor).dict()
        doctor_dict['weekly_schedule'] = weekly_schedule
        
        return DoctorWithSchedule(**doctor_dict)
    
    def check_availability(
        self,
        doctor_id: int,
        check_date: date,
        start_time: time,
        duration_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Check if doctor is available at specific date and time
        
        Args:
            doctor_id: Doctor ID
            check_date: Date to check
            start_time: Start time
            duration_minutes: Appointment duration
            
        Returns:
            Availability information
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor or not doctor.is_available or not doctor.is_active:
            return {
                'available': False,
                'reason': 'Doctor is not available'
            }
        
        # Check day availability
        day_name = check_date.strftime('%A').lower()
        schedule = doctor.availability_schedule or {}
        day_schedule = schedule.get(day_name, {})
        
        if not day_schedule or not day_schedule.get('is_available', False):
            return {
                'available': False,
                'reason': f'Doctor is not available on {day_name.capitalize()}'
            }
        
        # Parse schedule times
        schedule_start = time.fromisoformat(day_schedule['start_time'])
        schedule_end = time.fromisoformat(day_schedule['end_time'])
        
        # Calculate end time
        end_time = (
            datetime.combine(check_date, start_time) + 
            timedelta(minutes=duration_minutes)
        ).time()
        
        # Check if within working hours
        if start_time < schedule_start or end_time > schedule_end:
            return {
                'available': False,
                'reason': 'Time is outside doctor\'s working hours'
            }
        
        # Check break time if exists
        if day_schedule.get('break_start') and day_schedule.get('break_end'):
            break_start = time.fromisoformat(day_schedule['break_start'])
            break_end = time.fromisoformat(day_schedule['break_end'])
            
            # Check if appointment overlaps with break
            if not (end_time <= break_start or start_time >= break_end):
                return {
                    'available': False,
                    'reason': 'Time conflicts with doctor\'s break'
                }
        
        # Check for conflicting appointments
        conflicting_appointments = (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == check_date,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.IN_PROGRESS
                    ])
                )
            )
            .all()
        )
        
        for apt in conflicting_appointments:
            apt_start = apt.appointment_time
            apt_duration = apt.duration_minutes or doctor.average_consultation_time
            apt_end = (
                datetime.combine(check_date, apt_start) + 
                timedelta(minutes=apt_duration)
            ).time()
            
            # Check if times overlap
            if not (end_time <= apt_start or start_time >= apt_end):
                return {
                    'available': False,
                    'reason': 'Time slot is already booked'
                }
        
        return {
            'available': True,
            'doctor_id': doctor_id,
            'date': check_date.isoformat(),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
    
    def get_available_slots(
        self,
        doctor_id: int,
        check_date: date,
        slot_duration: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all available time slots for a doctor on a specific date
        
        Args:
            doctor_id: Doctor ID
            check_date: Date to check
            slot_duration: Slot duration in minutes (uses doctor's average if not provided)
            
        Returns:
            List of available time slots
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor or not doctor.is_available or not doctor.is_active:
            return []
        
        duration = slot_duration or doctor.average_consultation_time
        
        # Get day schedule
        day_name = check_date.strftime('%A').lower()
        schedule = doctor.availability_schedule or {}
        day_schedule = schedule.get(day_name, {})
        
        if not day_schedule or not day_schedule.get('is_available', False):
            return []
        
        # Parse schedule times
        schedule_start = time.fromisoformat(day_schedule['start_time'])
        schedule_end = time.fromisoformat(day_schedule['end_time'])
        
        break_start = None
        break_end = None
        if day_schedule.get('break_start') and day_schedule.get('break_end'):
            break_start = time.fromisoformat(day_schedule['break_start'])
            break_end = time.fromisoformat(day_schedule['break_end'])
        
        # Get existing appointments
        appointments = (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == check_date,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.IN_PROGRESS
                    ])
                )
            )
            .all()
        )
        
        # Generate all possible slots
        slots = []
        current_time = schedule_start
        
        while current_time < schedule_end:
            slot_end = (
                datetime.combine(check_date, current_time) + 
                timedelta(minutes=duration)
            ).time()
            
            if slot_end > schedule_end:
                break
            
            # Check if slot is during break
            is_during_break = False
            if break_start and break_end:
                if not (slot_end <= break_start or current_time >= break_end):
                    is_during_break = True
            
            # Check if slot conflicts with appointment
            is_booked = False
            for apt in appointments:
                apt_start = apt.appointment_time
                apt_duration = apt.duration_minutes or doctor.average_consultation_time
                apt_end = (
                    datetime.combine(check_date, apt_start) + 
                    timedelta(minutes=apt_duration)
                ).time()
                
                if not (slot_end <= apt_start or current_time >= apt_end):
                    is_booked = True
                    break
            
            if not is_during_break and not is_booked:
                slots.append({
                    'start_time': current_time.isoformat(),
                    'end_time': slot_end.isoformat(),
                    'available': True
                })
            
            # Move to next slot
            current_time = (
                datetime.combine(check_date, current_time) + 
                timedelta(minutes=duration)
            ).time()
        
        return slots
    
    # ============================================================================
    # STATISTICS AND REPORTING
    # ============================================================================
    
    def get_doctor_stats(
        self,
        doctor_id: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Optional[DoctorStats]:
        """
        Get doctor statistics and performance metrics
        
        Args:
            doctor_id: Doctor ID
            from_date: Start date for stats (defaults to 30 days ago)
            to_date: End date for stats (defaults to today)
            
        Returns:
            Doctor statistics or None if doctor not found
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return None
        
        # Set default date range
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)
        
        # Get appointments in date range
        appointments = (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .all()
        )
        
        total_appointments = len(appointments)
        completed_appointments = sum(
            1 for a in appointments if a.status == AppointmentStatus.COMPLETED
        )
        cancelled_appointments = sum(
            1 for a in appointments if a.status == AppointmentStatus.CANCELLED
        )
        
        # Today's appointments
        today = date.today()
        today_appointments = (
            self.db.query(func.count(Appointment.id))
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == today
                )
            )
            .scalar() or 0
        )
        
        # Total unique patients
        total_patients = (
            self.db.query(func.count(func.distinct(Appointment.patient_id)))
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .scalar() or 0
        )
        
        # Average rating (if feedback system exists)
        # Placeholder - would come from a ratings table
        average_rating = None
        
        return DoctorStats(
            total_appointments=total_appointments,
            completed_appointments=completed_appointments,
            cancelled_appointments=cancelled_appointments,
            average_rating=average_rating,
            total_patients=total_patients,
            today_appointments=today_appointments
        )
    
    def get_doctor_revenue(
        self,
        doctor_id: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get doctor's revenue statistics
        
        Args:
            doctor_id: Doctor ID
            from_date: Start date
            to_date: End date
            
        Returns:
            Revenue statistics
        """
        doctor = self.doctor_repo.get(doctor_id)
        
        if not doctor:
            return {
                'total_revenue': 0,
                'total_visits': 0,
                'average_per_visit': 0
            }
        
        # Set default date range
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)
        
        # Get revenue from visits
        revenue_data = (
            self.db.query(
                func.count(Visit.id).label('visit_count'),
                func.sum(Invoice.total_amount).label('total_revenue'),
                func.sum(Invoice.paid_amount).label('paid_revenue')
            )
            .join(Invoice, Invoice.visit_id == Visit.id)
            .filter(
                and_(
                    Visit.tenant_id == self.tenant_id,
                    Visit.doctor_id == doctor_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .first()
        )
        
        visit_count = revenue_data.visit_count or 0
        total_revenue = revenue_data.total_revenue or 0
        paid_revenue = revenue_data.paid_revenue or 0
        
        return {
            'total_revenue': total_revenue,
            'paid_revenue': paid_revenue,
            'pending_revenue': total_revenue - paid_revenue,
            'total_visits': visit_count,
            'average_per_visit': total_revenue // visit_count if visit_count > 0 else 0,
            'period_start': from_date.isoformat(),
            'period_end': to_date.isoformat()
        }
    
    # ============================================================================
    # SEARCH AND FILTERS
    # ============================================================================
    
    def search_doctors(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search doctors by name, specialization, or code
        
        Args:
            search_term: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with items and total count
        """
        doctors = self.doctor_repo.search_doctors(
            search_term=search_term,
            skip=skip,
            limit=limit
        )
        
        # Get total count for pagination
        query = self.db.query(Doctor).join(User).filter(
            and_(
                Doctor.tenant_id == self.tenant_id,
                or_(
                    User.first_name.ilike(f"%{search_term}%"),
                    User.last_name.ilike(f"%{search_term}%"),
                    Doctor.specialization.ilike(f"%{search_term}%"),
                    Doctor.doctor_code.ilike(f"%{search_term}%")
                )
            )
        )
        
        total = query.count()
        
        return {
            'items': [DoctorSchema.from_orm(doc) for doc in doctors],
            'total': total
        }
    
    def get_doctors_by_specialization(
        self,
        specialization: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[DoctorSchema]:
        """
        Get doctors by specialization
        
        Args:
            specialization: Specialization to filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of doctors
        """
        doctors = self.doctor_repo.get_by_specialization(
            specialization=specialization,
            skip=skip,
            limit=limit
        )
        
        return [DoctorSchema.from_orm(doc) for doc in doctors]
    
    def get_doctors_by_department(
        self,
        department_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[DoctorSchema]:
        """
        Get doctors by department
        
        Args:
            department_id: Department ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of doctors
        """
        doctors = self.doctor_repo.get_by_department(
            department_id=department_id,
            skip=skip,
            limit=limit
        )
        
        return [DoctorSchema.from_orm(doc) for doc in doctors]
    
    def get_available_doctors_for_date(
        self,
        check_date: date,
        specialization: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get doctors available on a specific date
        
        Args:
            check_date: Date to check
            specialization: Optional specialization filter
            
        Returns:
            List of available doctors with their slots
        """
        # Get available doctors
        query = self.db.query(Doctor).filter(
            and_(
                Doctor.tenant_id == self.tenant_id,
                Doctor.is_available == True,
                Doctor.is_active == True
            )
        )
        
        if specialization:
            query = query.filter(
                Doctor.specialization.ilike(f"%{specialization}%")
            )
        
        doctors = query.all()
        
        # Filter by day availability and get slots
        available_doctors = []
        day_name = check_date.strftime('%A').lower()
        
        for doctor in doctors:
            schedule = doctor.availability_schedule or {}
            day_schedule = schedule.get(day_name, {})
            
            if day_schedule and day_schedule.get('is_available', False):
                slots = self.get_available_slots(doctor.id, check_date)
                
                if slots:  # Only include if has available slots
                    doctor_dict = DoctorSchema.from_orm(doctor).dict()
                    doctor_dict['available_slots'] = len(slots)
                    doctor_dict['slots'] = slots
                    available_doctors.append(doctor_dict)
        
        return available_doctors
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_default_schedule(self) -> Dict[str, Any]:
        """Get default weekly schedule (Monday-Friday 9 AM - 5 PM)"""
        default_day = {
            'is_available': True,
            'start_time': '09:00:00',
            'end_time': '17:00:00',
            'slots': 16,  # 8 hours * 2 slots per hour
            'break_start': '13:00:00',
            'break_end': '14:00:00'
        }
        
        weekend_day = {
            'is_available': False,
            'start_time': None,
            'end_time': None,
            'slots': None,
            'break_start': None,
            'break_end': None
        }
        
        return {
            'monday': default_day.copy(),
            'tuesday': default_day.copy(),
            'wednesday': default_day.copy(),
            'thursday': default_day.copy(),
            'friday': default_day.copy(),
            'saturday': weekend_day.copy(),
            'sunday': weekend_day.copy()
        }
    
    def _parse_schedule_to_list(
        self,
        schedule: Dict[str, Any]
    ) -> List[DoctorAvailability]:
        """Convert schedule dictionary to list of DoctorAvailability objects"""
        schedule_list = []
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day in days:
            day_schedule = schedule.get(day, {})
            
            availability = DoctorAvailability(
                day=day,
                is_available=day_schedule.get('is_available', False),
                start_time=time.fromisoformat(day_schedule['start_time']) 
                    if day_schedule.get('start_time') else None,
                end_time=time.fromisoformat(day_schedule['end_time']) 
                    if day_schedule.get('end_time') else None,
                slots=day_schedule.get('slots'),
                break_start=time.fromisoformat(day_schedule['break_start']) 
                    if day_schedule.get('break_start') else None,
                break_end=time.fromisoformat(day_schedule['break_end']) 
                    if day_schedule.get('break_end') else None
            )
            
            schedule_list.append(availability)
        
        return schedule_list
    
    def _calculate_working_minutes(
        self,
        start_time: time,
        end_time: time,
        break_start: Optional[time] = None,
        break_end: Optional[time] = None
    ) -> int:
        """Calculate total working minutes in a day"""
        # Calculate total minutes
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)
        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        # Subtract break time if exists
        if break_start and break_end:
            break_start_dt = datetime.combine(date.today(), break_start)
            break_end_dt = datetime.combine(date.today(), break_end)
            break_minutes = int((break_end_dt - break_start_dt).total_seconds() / 60)
            total_minutes -= break_minutes
        
        return total_minutes