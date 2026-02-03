from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from repositories.patient import PatientRepository
from repositories.appointment import AppointmentRepository
from repositories.visit import VisitRepository
from repositories.billing import InvoiceRepository
from schemas.patient import PatientCreate, PatientUpdate
from models.patient import Patient
from services.base_service import BaseService

class PatientService(BaseService):
    """Patient management service"""
    
    def __init__(
        self,
        db: Session,
        tenant_id: int,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, tenant_id, current_user_id)
        self.patient_repo = PatientRepository(db, tenant_id, current_user_id)
        self.appointment_repo = AppointmentRepository(db, tenant_id, current_user_id)
        self.visit_repo = VisitRepository(db, tenant_id, current_user_id)
        self.invoice_repo = InvoiceRepository(db, tenant_id, current_user_id)
    
    def create_patient(self, patient_in: PatientCreate) -> Patient:
        """Create new patient"""
        # Check for duplicate
        duplicate = self.patient_repo.check_duplicate(
            patient_in.phone,
            patient_in.email
        )
        
        if duplicate:
            raise ValueError(f"Patient with phone {patient_in.phone} already exists")
        
        # Generate patient code
        patient_code = self.patient_repo.generate_patient_code()
        
        # Create patient
        patient_data = patient_in.dict()
        patient_data['patient_code'] = patient_code
        patient_data['registration_date'] = datetime.utcnow().date()
        
        patient = self.patient_repo.create(patient_data)
        self.commit()
        
        return patient
    
    def get_patient(self, patient_id: int) -> Optional[Patient]:
        """Get patient by ID"""
        return self.patient_repo.get(patient_id)
    
    def get_patients(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get list of patients"""
        if search:
            patients = self.patient_repo.search_patients(search, skip, limit)
            total = len(patients)  # Approximate
        else:
            patients = self.patient_repo.get_multi(skip, limit, filters)
            total = self.patient_repo.count(filters)
        
        return {
            'items': patients,
            'total': total
        }
    
    def update_patient(self, patient_id: int, patient_in: PatientUpdate) -> Optional[Patient]:
        """Update patient information"""
        patient = self.patient_repo.get(patient_id)
        if not patient:
            return None
        
        # Check for duplicate if phone/email changed
        update_data = patient_in.dict(exclude_unset=True)
        
        if 'phone' in update_data or 'email' in update_data:
            phone = update_data.get('phone', patient.phone)
            email = update_data.get('email', patient.email)
            
            duplicate = self.patient_repo.check_duplicate(phone, email, patient_id)
            if duplicate:
                raise ValueError("Patient with this phone/email already exists")
        
        patient = self.patient_repo.update(patient_id, update_data)
        self.commit()
        
        return patient
    
    def delete_patient(self, patient_id: int, soft: bool = True) -> bool:
        """Delete patient"""
        success = self.patient_repo.delete(patient_id, soft=soft)
        if success:
            self.commit()
        return success
    
    def get_patient_with_history(self, patient_id: int) -> Optional[Dict[str, Any]]:
        """Get patient with medical history"""
        patient = self.patient_repo.get(patient_id)
        if not patient:
            return None
        
        # Get recent visits
        recent_visits = self.visit_repo.get_patient_history(patient_id, limit=10)
        
        # Get upcoming appointments
        upcoming_appointments = self.appointment_repo.get_upcoming_appointments(
            days=30,
            patient_id=patient_id
        )
        
        # Get statistics
        stats = self.get_patient_stats(patient_id)
        
        return {
            **patient.__dict__,
            'recent_visits': recent_visits,
            'upcoming_appointments': upcoming_appointments,
            'stats': stats
        }
    
    def get_patient_stats(self, patient_id: int) -> Dict[str, Any]:
        """Get patient statistics"""
        # Total visits
        total_visits = self.visit_repo.count({'patient_id': patient_id})
        
        # Last visit
        visits = self.visit_repo.get_by_patient(patient_id, limit=1)
        last_visit_date = visits[0].visit_date if visits else None
        
        # Total spent and pending balance
        invoices = self.invoice_repo.get_by_patient(patient_id)
        total_spent = sum(inv.paid_amount for inv in invoices)
        pending_balance = sum(inv.balance_amount for inv in invoices)
        
        # Upcoming appointments
        upcoming = self.appointment_repo.get_upcoming_appointments(
            days=30,
            patient_id=patient_id
        )
        
        return {
            'total_visits': total_visits,
            'last_visit_date': last_visit_date,
            'total_spent': total_spent,
            'pending_balance': pending_balance,
            'upcoming_appointments': len(upcoming)
        }
    
    def search_patients(self, search_params: Dict[str, Any]) -> List[Patient]:
        """Advanced patient search"""
        # Implement advanced search based on multiple criteria
        patients = []
        
        if search_params.get('query'):
            patients = self.patient_repo.search_patients(search_params['query'])
        
        # Apply filters
        if search_params.get('gender'):
            patients = [p for p in patients if p.gender == search_params['gender']]
        
        if search_params.get('min_age') or search_params.get('max_age'):
            patients = self.patient_repo.get_by_age_range(
                search_params.get('min_age'),
                search_params.get('max_age')
            )
        
        return patients