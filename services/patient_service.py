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
        current_user_id: Optional[int] = None,
    ):
        super().__init__(db, tenant_id, current_user_id)
        self.patient_repo = PatientRepository(db, tenant_id, current_user_id)
        self.appointment_repo = AppointmentRepository(db, tenant_id, current_user_id)
        self.visit_repo = VisitRepository(db, tenant_id, current_user_id)
        self.invoice_repo = InvoiceRepository(db, tenant_id, current_user_id)

    # services/patient_service.py
    def create_patient(self, patient_in: PatientCreate) -> Patient:
        duplicate = self.patient_repo.check_duplicate(
            patient_in.phone,
            patient_in.email,
        )
        if duplicate:
            raise ValueError(f"Patient with phone {patient_in.phone} already exists")

        tenant = self.tenant_repo.get(self.tenant_id)  # or however you access tenant
        max_patients = tenant.enabled_features.get('max_patients', 50)
        if max_patients != -1:
            current_count = self.patient_repo.count({})
            if current_count >= max_patients:
                raise ValueError(f"Patient limit ({max_patients}) reached for your subscription tier")

        patient_code = self.patient_repo.generate_patient_code()

        patient_data = patient_in.dict()
        patient_data["patient_code"] = patient_code
        patient_data["registration_date"] = datetime.utcnow()  # ✅ datetime instead of date
        patient_data["created_at"] = datetime.utcnow()  # ✅ Explicitly set created_at

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
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get list of patients"""
        if search:
            patients = self.patient_repo.search_patients(search, skip, limit)
            # BUG FIX 1: len(patients) is wrong for paginated results —
            # it returns at most `limit` items, so the total shown to the
            # frontend was capped at page_size (e.g. always "20 of 20").
            # Use count() with a search filter instead so pagination is correct.
            total = self.patient_repo.count_search(search)
        else:
            patients = self.patient_repo.get_multi(skip, limit, filters)
            total = self.patient_repo.count(filters)

        return {"items": patients, "total": total}

    def update_patient(
        self, patient_id: int, patient_in: PatientUpdate
    ) -> Optional[Patient]:
        """Update patient information"""
        patient = self.patient_repo.get(patient_id)
        if not patient:
            return None

        update_data = patient_in.dict(exclude_unset=True)

        if "phone" in update_data or "email" in update_data:
            phone = update_data.get("phone", patient.phone)
            email = update_data.get("email", patient.email)
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

        recent_visits = self.visit_repo.get_patient_history(patient_id, limit=10)
        upcoming_appointments = self.appointment_repo.get_upcoming_appointments(
            days=30, patient_id=patient_id
        )
        stats = self.get_patient_stats(patient_id)

        return {
            **patient.__dict__,
            "recent_visits": recent_visits,
            "upcoming_appointments": upcoming_appointments,
            "stats": stats,
        }

    def get_patient_stats(self, patient_id: int) -> Dict[str, Any]:
        """Get patient statistics"""
        total_visits = self.visit_repo.count({"patient_id": patient_id})

        visits = self.visit_repo.get_by_patient(patient_id, limit=1)
        last_visit_date = visits[0].visit_date if visits else None

        invoices = self.invoice_repo.get_by_patient(patient_id)
        total_spent = sum(inv.paid_amount for inv in invoices)
        pending_balance = sum(inv.balance_amount for inv in invoices)

        upcoming = self.appointment_repo.get_upcoming_appointments(
            days=30, patient_id=patient_id
        )

        return {
            "total_visits": total_visits,
            "last_visit_date": last_visit_date,
            "total_spent": total_spent,
            "pending_balance": pending_balance,
            "upcoming_appointments": len(upcoming),
        }

    def search_patients(self, search_params: Dict[str, Any]) -> List[Patient]:
        """Advanced patient search"""
        # BUG FIX 2: Original applied gender/age filters AFTER fetching results
        # in Python — O(n) memory, ignores pagination, and age filter replaced
        # the query results entirely instead of intersecting them.
        # Pass all criteria down to the repo so the DB does the filtering.
        query = search_params.get("query")
        gender = search_params.get("gender")
        min_age = search_params.get("min_age")
        max_age = search_params.get("max_age")

        if min_age is not None or max_age is not None:
            # Age-range search (repo translates age → date_of_birth range)
            return self.patient_repo.get_by_age_range(
                min_age=min_age,
                max_age=max_age,
                gender=gender,
                search=query,
            )

        if query:
            patients = self.patient_repo.search_patients(query)
            if gender:
                patients = [p for p in patients if p.gender.value == gender]
            return patients

        # No query, no age — just filter by gender if provided
        filters: Dict[str, Any] = {}
        if gender:
            filters["gender"] = gender
        return self.patient_repo.get_multi(0, 100, filters)