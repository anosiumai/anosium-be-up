from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session

from models.visit import Visit, VisitStatus
from models.patient import Patient
from models.doctor import Doctor
from models.appointment import Appointment
from schemas.visit import VisitCreate, VisitUpdate
from repositories.visit import VisitRepository


class VisitService:
    """Service layer for Visit business logic"""

    def __init__(
        self,
        db: Session,
        tenant_id: int,
        current_user_id: Optional[int] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
        self.repo = VisitRepository(db, tenant_id, current_user_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_patient(self, patient_id: int) -> Patient:
        """Resolve & validate patient belongs to tenant."""
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.tenant_id == self.tenant_id)
            .first()
        )
        if not patient:
            raise ValueError(f"Patient with id {patient_id} not found")
        return patient

    def _get_doctor(self, doctor_id: int) -> Doctor:
        """Resolve & validate doctor belongs to tenant."""
        doctor = (
            self.db.query(Doctor)
            .filter(Doctor.id == doctor_id, Doctor.tenant_id == self.tenant_id)
            .first()
        )
        if not doctor:
            raise ValueError(f"Doctor with id {doctor_id} not found")
        return doctor

    def _get_appointment(self, appointment_id: int) -> Appointment:
        """Resolve & validate appointment belongs to tenant and is not already linked."""
        appointment = (
            self.db.query(Appointment)
            .filter(
                Appointment.id == appointment_id,
                Appointment.tenant_id == self.tenant_id,
            )
            .first()
        )
        if not appointment:
            raise ValueError(f"Appointment with id {appointment_id} not found")

        # appointment_id is unique on Visit — guard against double-linking
        existing = self.repo.get_by_appointment(appointment_id)
        if existing:
            raise ValueError(
                f"Appointment {appointment_id} is already linked to visit {existing.visit_code}"
            )
        return appointment

    def _validate_follow_up(self, data: dict) -> None:
        """Ensure follow_up_date is provided when follow_up_required is True."""
        if data.get("follow_up_required") and not data.get("follow_up_date"):
            raise ValueError("follow_up_date is required when follow_up_required is True")

        follow_up_date = data.get("follow_up_date")
        if follow_up_date and follow_up_date < date.today():
            raise ValueError("follow_up_date cannot be in the past")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_visit(self, visit_in: VisitCreate) -> Visit:
        """
        Create a new visit record.

        Validates:
          - patient & doctor exist within the tenant
          - appointment (optional) exists, belongs to tenant, and is not already used
          - follow-up consistency
        """
        # foreign-key validation
        self._get_patient(visit_in.patient_id)
        self._get_doctor(visit_in.doctor_id)

        if visit_in.appointment_id:
            self._get_appointment(visit_in.appointment_id)

        # follow-up consistency
        self._validate_follow_up(visit_in.model_dump())

        # generate unique visit code
        visit_code = self.repo.generate_visit_code()

        # build the ORM instance
        visit = Visit(
            tenant_id=self.tenant_id,
            patient_id=visit_in.patient_id,
            doctor_id=visit_in.doctor_id,
            appointment_id=visit_in.appointment_id,
            visit_code=visit_code,
            visit_date=datetime.utcnow(),
            status=VisitStatus.IN_PROGRESS,
            chief_complaint=visit_in.chief_complaint,
            symptoms=visit_in.symptoms,
            vitals=visit_in.vitals.model_dump() if visit_in.vitals else {},
            diagnosis=visit_in.diagnosis,
            treatment_plan=visit_in.treatment_plan,
            prescriptions=[p.model_dump() for p in visit_in.prescriptions],
            lab_tests_ordered=[lt.model_dump() for lt in visit_in.lab_tests_ordered],
            procedures_performed=visit_in.procedures_performed,
            follow_up_required=visit_in.follow_up_required,
            follow_up_date=visit_in.follow_up_date,
            follow_up_notes=visit_in.follow_up_notes,
        )

        self.db.add(visit)
        self.db.commit()
        self.db.refresh(visit)
        return visit

    def get_visit_with_details(self, visit_id: int) -> Optional[Visit]:
        """Fetch a single visit with all eager-loaded relationships."""
        return self.repo.get_with_details(visit_id)

    def get_visits(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Paginated visit listing with optional doctor / patient filters.

        Returns ``{"items": [...], "total": int}``.
        """
        filters = filters or {}

        query = self.db.query(Visit).filter(Visit.tenant_id == self.tenant_id)

        if "doctor_id" in filters:
            query = query.filter(Visit.doctor_id == filters["doctor_id"])

        if "patient_id" in filters:
            query = query.filter(Visit.patient_id == filters["patient_id"])

        # total before pagination (needed for page math in the router)
        total = query.count()

        items = (
            query.order_by(Visit.visit_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total}

    def update_visit(self, visit_id: int, visit_in: VisitUpdate) -> Optional[Visit]:
        """
        Partial update of an existing visit.

        Only non-None fields from the payload are applied.  If status is being
        moved to COMPLETED the ``completed_at`` timestamp is stamped automatically.
        """
        visit = self.repo.get_with_details(visit_id)
        if not visit:
            return None

        update_data = visit_in.model_dump(exclude_unset=True)

        # --- nested Pydantic → plain-dict coercion for JSON columns ----------
        if "vitals" in update_data and update_data["vitals"] is not None:
            # vitals may arrive as a Vitals model instance when coming from
            # validated VisitUpdate; normalise to a plain dict for the JSON col.
            vitals_raw = update_data["vitals"]
            update_data["vitals"] = (
                vitals_raw.model_dump() if hasattr(vitals_raw, "model_dump") else vitals_raw
            )

        if "prescriptions" in update_data and update_data["prescriptions"] is not None:
            update_data["prescriptions"] = [
                p.model_dump() if hasattr(p, "model_dump") else p
                for p in update_data["prescriptions"]
            ]

        if "lab_tests_ordered" in update_data and update_data["lab_tests_ordered"] is not None:
            update_data["lab_tests_ordered"] = [
                lt.model_dump() if hasattr(lt, "model_dump") else lt
                for lt in update_data["lab_tests_ordered"]
            ]

        # --- follow-up consistency check on the *merged* state ---------------
        merged = {
            "follow_up_required": update_data.get(
                "follow_up_required", visit.follow_up_required
            ),
            "follow_up_date": update_data.get("follow_up_date", visit.follow_up_date),
        }
        self._validate_follow_up(merged)

        # --- status transition guard -----------------------------------------
        new_status = update_data.get("status")
        if new_status and new_status == VisitStatus.COMPLETED and visit.status != VisitStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow()

        # --- apply updates ----------------------------------------------------
        for key, value in update_data.items():
            setattr(visit, key, value)

        self.db.commit()
        self.db.refresh(visit)
        return visit

    # ------------------------------------------------------------------
    # domain actions
    # ------------------------------------------------------------------

    def get_patient_visit_history(
        self, patient_id: int, limit: int = 10
    ) -> List[Visit]:
        """Return completed visits for a patient, most recent first."""
        self._get_patient(patient_id)          # 404-safe validation
        return self.repo.get_patient_history(patient_id, limit=limit)

    def complete_visit(self, visit_id: int) -> Optional[Visit]:
        """
        Transition a visit to COMPLETED status.

        Raises ValueError if the visit is already completed or is not in a
        state that can legally move to COMPLETED (i.e. must be IN_PROGRESS).
        """
        visit = self.repo.get_with_details(visit_id)
        if not visit:
            return None

        if visit.status == VisitStatus.COMPLETED:
            raise ValueError(f"Visit {visit.visit_code} is already completed")

        if visit.status != VisitStatus.IN_PROGRESS:
            raise ValueError(
                f"Visit {visit.visit_code} cannot be completed from status '{visit.status.value}'. "
                f"Only visits with status 'in_progress' can be completed."
            )

        visit.status = VisitStatus.COMPLETED
        visit.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(visit)
        return visit

    # ------------------------------------------------------------------
    # read-only queries (exposed for dashboards / reports)
    # ------------------------------------------------------------------

    def get_today_visits(
        self, doctor_id: Optional[int] = None
    ) -> List[Visit]:
        """All visits recorded today, optionally scoped to a doctor."""
        return self.repo.get_today_visits(doctor_id=doctor_id)

    def get_pending_visits(
        self, doctor_id: Optional[int] = None, limit: int = 50
    ) -> List[Visit]:
        """Visits currently in IN_PROGRESS status."""
        return self.repo.get_pending_visits(doctor_id=doctor_id, limit=limit)

    def get_follow_up_required(
        self, days_ahead: int = 30, limit: int = 100
    ) -> List[Visit]:
        """Visits whose follow-up date falls within *days_ahead* days."""
        return self.repo.get_follow_up_required(days_ahead=days_ahead, limit=limit)

    def search_by_diagnosis(
        self, term: str, skip: int = 0, limit: int = 100
    ) -> List[Visit]:
        """Full-text (ILIKE) search across the diagnosis column."""
        return self.repo.search_by_diagnosis(term, skip=skip, limit=limit)

    def get_visit_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate stats: totals, status breakdown, follow-up count."""
        return self.repo.get_statistics(from_date=from_date, to_date=to_date)

    def count_visits_by_status(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Status → count mapping, optionally bounded by date range."""
        return self.repo.count_by_status(from_date=from_date, to_date=to_date)