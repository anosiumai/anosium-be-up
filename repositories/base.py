from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text
from datetime import datetime, date, time
import enum
import logging

from models.audit import AuditLog, AuditAction
from core.database import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


# ---------------------------------------------------------------------------
# Sequence registry
#
# Every code generator that previously used count()+1 now calls
# _next_sequence_value().  On first call the sequence is created if it doesn't
# already exist (idempotent DDL), so no separate migration is required for
# existing deployments.
#
# Naming convention:  seq_<tablename>_code
#   patient_code      → seq_patients_code
#   doctor_code       → seq_doctors_code
#   appointment_code  → seq_appointments_code
#   visit_code        → seq_visits_code
#   invoice_number    → seq_invoices_number
#   payment_number    → seq_payments_number
#
# Each sequence starts at 1 and increments by 1.  Values are tenant-agnostic
# (globally unique across all tenants), which is the right trade-off:
#   • No race condition — nextval() is atomic at the DB level.
#   • Codes may have gaps (rolled-back transactions do not recycle values) —
#     this is normal and expected for audit-safe sequential identifiers.
#   • Per-tenant sequences would require runtime DDL per new tenant; global
#     sequences are simpler and still guarantee uniqueness.
# ---------------------------------------------------------------------------

_SEQUENCE_NAMES: Dict[str, str] = {
    "patients":     "seq_patients_code",
    "doctors":      "seq_doctors_code",
    "appointments": "seq_appointments_code",
    "visits":       "seq_visits_code",
    "invoices":     "seq_invoices_number",
    "payments":     "seq_payments_number",
}


def _next_sequence_value(db: Session, sequence_name: str) -> int:
    """
    Return the next value from a PostgreSQL sequence, creating it on the fly
    if it does not yet exist.

    This replaces every ``count() + 1`` pattern in the codebase.  PostgreSQL's
    ``nextval()`` is atomic — two concurrent transactions calling this function
    for the same sequence are guaranteed to receive different values.

    Args:
        db:            SQLAlchemy session (used to execute the SQL).
        sequence_name: Bare sequence name (e.g. "seq_patients_code").

    Returns:
        Next integer value from the sequence (always ≥ 1).
    """
    # CREATE SEQUENCE IF NOT EXISTS is idempotent — safe to call every time.
    db.execute(
        text(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START 1 INCREMENT 1")
    )
    row = db.execute(text(f"SELECT nextval('{sequence_name}')")).fetchone()
    return int(row[0])


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing:

    - Automatic tenant isolation on every query
    - Audit logging baked into create / update / delete
    - Soft deletes
    - Common CRUD helpers
    - Race-condition-free code generation via PostgreSQL sequences

    Constructor parameter order
    ---------------------------
    (db, model, tenant_id, current_user_id)

    Child repositories call::

        super().__init__(db, MyModel, tenant_id, current_user_id)
    """

    def __init__(
        self,
        db: Session,
        model: Type[ModelType],
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None,
    ):
        self.db = db
        self.model = model
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _apply_tenant_filter(self, query):
        """Append a WHERE tenant_id = … clause when the model has that column."""
        if hasattr(self.model, "tenant_id") and self.tenant_id is not None:
            return query.filter(self.model.tenant_id == self.tenant_id)
        return query

    @staticmethod
    def _serialize_values(values: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Recursively convert non-JSON-serialisable Python types so that audit
        log values can be stored in a JSON column without raising TypeError.

        Handles: datetime, date, time, enum.Enum, nested dict.
        """
        if not values:
            return values

        serialized: Dict[str, Any] = {}
        for key, value in values.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, date):
                serialized[key] = value.isoformat()
            elif isinstance(value, time):
                serialized[key] = value.strftime("%H:%M:%S")
            elif isinstance(value, enum.Enum):
                serialized[key] = value.value
            elif isinstance(value, dict):
                serialized[key] = BaseRepository._serialize_values(value)
            else:
                serialized[key] = value

        return serialized

    def _log_audit(
        self,
        action: AuditAction,
        resource_id: int,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
    ) -> None:
        """
        Write an AuditLog row for the current operation.

        Audit failures are logged at ERROR level and re-raised in strict mode
        (HIPAA-aligned).  In non-strict mode the exception is swallowed so that
        a logging hiccup never rolls back a clinical operation.

        Note: flush() is intentionally used (not commit()) so that audit rows
        participate in the same transaction as the operation they describe.  If
        the outer transaction rolls back, the audit row rolls back too — which
        is correct: a rolled-back operation should not produce an audit trail.
        """
        if not self.tenant_id:
            return

        try:
            audit_log = AuditLog(
                tenant_id=self.tenant_id,
                user_id=self.current_user_id,
                action=action,
                resource_type=self.model.__tablename__,
                resource_id=resource_id,
                old_values=self._serialize_values(old_values),
                new_values=self._serialize_values(new_values),
                changes_summary=changes_summary,
                created_at=datetime.utcnow(),
            )
            self.db.add(audit_log)
            self.db.flush()

        except Exception as exc:
            # Always log — never silently discard compliance events.
            logger.error(
                "Audit log write failed for %s id=%s action=%s: %s",
                self.model.__tablename__,
                resource_id,
                action,
                exc,
                exc_info=True,
            )
            # Re-raise in strict compliance mode so the caller can decide
            # whether to surface a 500 or continue.  Production deployments
            # targeting HIPAA should catch this at the service layer.
            raise

    # ------------------------------------------------------------------
    # sequence-based code generators
    # ------------------------------------------------------------------

    def _next_seq(self, table_name: str) -> int:
        """
        Return the next value from the sequence registered for *table_name*.

        Raises KeyError if *table_name* has no registered sequence — this is a
        programmer error (add it to _SEQUENCE_NAMES) not a runtime error.
        """
        sequence_name = _SEQUENCE_NAMES[table_name]
        return _next_sequence_value(self.db, sequence_name)

    def generate_patient_code(self) -> str:
        """
        Generate a globally unique patient code.

        Format: PAT-{zero-padded 5-digit sequence number}
        Example: PAT-00042

        Old approach (BROKEN under concurrency):
            count = db.query(func.count(Patient.id)).scalar() or 0
            return f"PAT-{count + 1:05d}"  # ← two requests get same count

        New approach (atomic):
            Uses PostgreSQL sequence — nextval() is serialised at the DB level.
        """
        n = self._next_seq("patients")
        return f"PAT-{n:05d}"

    def generate_doctor_code(self) -> str:
        """
        Generate a globally unique doctor code.

        Format: DOC-{zero-padded 5-digit sequence number}
        Example: DOC-00007
        """
        n = self._next_seq("doctors")
        return f"DOC-{n:05d}"

    def generate_appointment_code(self) -> str:
        """
        Generate a globally unique appointment code.

        Format: APT-{YYYYMMDD}-{zero-padded 4-digit sequence number}
        Example: APT-20260613-0001

        The date prefix aids human readability; uniqueness is guaranteed by
        the sequence, not by the date (a new day does not reset the counter).
        """
        n = self._next_seq("appointments")
        today = date.today()
        return f"APT-{today.strftime('%Y%m%d')}-{n:04d}"

    def generate_visit_code(self) -> str:
        """
        Generate a globally unique visit code.

        Format: VST-{YYYYMMDD}-{zero-padded 4-digit sequence number}
        Example: VST-20260613-0003
        """
        n = self._next_seq("visits")
        today = date.today()
        return f"VST-{today.strftime('%Y%m%d')}-{n:04d}"

    def generate_invoice_number(self) -> str:
        """
        Generate a globally unique invoice number.

        Format: INV-{YYYYMMDD}-{zero-padded 4-digit sequence number}
        Example: INV-20260613-0012
        """
        n = self._next_seq("invoices")
        today = date.today()
        return f"INV-{today.strftime('%Y%m%d')}-{n:04d}"

    def generate_payment_number(self) -> str:
        """
        Generate a globally unique payment number.

        Format: PAY-{YYYYMMDD}-{zero-padded 4-digit sequence number}
        Example: PAY-20260613-0005
        """
        n = self._next_seq("payments")
        today = date.today()
        return f"PAY-{today.strftime('%Y%m%d')}-{n:04d}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get(self, id: int) -> Optional[ModelType]:
        """Fetch a single record by primary key, scoped to the current tenant."""
        query = self.db.query(self.model).filter(self.model.id == id)
        query = self._apply_tenant_filter(query)
        return query.first()

    def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[ModelType]:
        """
        Paginated list with optional equality filters and ordering.

        ``order_by`` accepts a field name (ascending) or ``-field`` (descending).
        Records with ``is_active = False`` are excluded by default.
        """
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)

        if hasattr(self.model, "is_active") and not include_inactive:
            query = query.filter(self.model.is_active == True)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)

        if order_by:
            if order_by.startswith("-"):
                query = query.order_by(desc(getattr(self.model, order_by[1:])))
            else:
                query = query.order_by(getattr(self.model, order_by))
        elif hasattr(self.model, "created_at"):
            query = query.order_by(desc(self.model.created_at))

        return query.offset(skip).limit(limit).all()

    def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        include_inactive: bool = False,
    ) -> int:
        """Count records matching the given filters, scoped to the current tenant."""
        query = self.db.query(func.count(self.model.id))
        query = self._apply_tenant_filter(query)

        if hasattr(self.model, "is_active") and not include_inactive:
            query = query.filter(self.model.is_active == True)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)

        return query.scalar()

    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """
        Insert a new record.

        Automatically stamps ``tenant_id`` and ``created_by`` when the model
        has those columns and the values are not already present in *obj_in*.
        Writes an audit log row in the same transaction.
        """
        if (
            hasattr(self.model, "tenant_id")
            and "tenant_id" not in obj_in
            and self.tenant_id
        ):
            obj_in["tenant_id"] = self.tenant_id

        if (
            hasattr(self.model, "created_by")
            and "created_by" not in obj_in
            and self.current_user_id
        ):
            obj_in["created_by"] = self.current_user_id

        # Explicitly set is_active=True when the model supports it and the
        # caller didn't override it — prevents newly created records from being
        # invisible to get_multi() which filters on is_active by default.
        if hasattr(self.model, "is_active") and "is_active" not in obj_in:
            obj_in["is_active"] = True

        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.flush()
        self.db.refresh(db_obj)

        self._log_audit(
            AuditAction.CREATE,
            db_obj.id,
            new_values=obj_in,
            changes_summary=f"Created {self.model.__tablename__} id={db_obj.id}",
        )

        return db_obj

    def update(
        self,
        id: int,
        obj_in: Dict[str, Any],
        skip_audit: bool = False,
    ) -> Optional[ModelType]:
        """
        Partial update — only keys present in *obj_in* are written.

        Captures old values for the audit trail before applying changes.
        """
        db_obj = self.get(id)
        if not db_obj:
            return None

        old_values: Dict[str, Any] = {
            key: getattr(db_obj, key)
            for key in obj_in
            if hasattr(db_obj, key)
        }

        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()

        self.db.flush()
        self.db.refresh(db_obj)

        if not skip_audit:
            changes = [f"{k}: {old_values.get(k)} → {v}" for k, v in obj_in.items()]
            self._log_audit(
                AuditAction.UPDATE,
                id,
                old_values=old_values,
                new_values=obj_in,
                changes_summary=f"Updated {', '.join(changes)}",
            )

        return db_obj

    def delete(self, id: int, soft: bool = True) -> bool:
        """
        Remove a record.

        ``soft=True`` (default): sets ``is_active = False`` and stamps
        ``updated_at``.  The row is preserved for audit and recovery purposes.

        ``soft=False``: hard delete.  Use only when data-retention policy
        explicitly permits removal (e.g. GDPR erasure request).
        """
        db_obj = self.get(id)
        if not db_obj:
            return False

        if soft and hasattr(db_obj, "is_active"):
            db_obj.is_active = False
            if hasattr(db_obj, "updated_at"):
                db_obj.updated_at = datetime.utcnow()
            self.db.flush()
            self._log_audit(
                AuditAction.DELETE,
                id,
                changes_summary=f"Soft-deleted {self.model.__tablename__} id={id}",
            )
        else:
            # Log before delete so resource_id still means something.
            self._log_audit(
                AuditAction.DELETE,
                id,
                changes_summary=f"Hard-deleted {self.model.__tablename__} id={id}",
            )
            self.db.delete(db_obj)
            self.db.flush()

        return True

    def exists(self, id: int) -> bool:
        """Return True if a record with *id* exists in the current tenant."""
        query = self.db.query(self.model.id).filter(self.model.id == id)
        query = self._apply_tenant_filter(query)
        return query.first() is not None

    def bulk_create(self, objs_in: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Insert multiple records efficiently.

        Uses ``bulk_save_objects`` for performance.  No per-row audit logs are
        written — callers that require audit trails should use ``create()`` in
        a loop instead.
        """
        db_objs = []
        for obj_in in objs_in:
            if (
                hasattr(self.model, "tenant_id")
                and "tenant_id" not in obj_in
                and self.tenant_id
            ):
                obj_in["tenant_id"] = self.tenant_id

            if hasattr(self.model, "is_active") and "is_active" not in obj_in:
                obj_in["is_active"] = True

            db_objs.append(self.model(**obj_in))

        self.db.bulk_save_objects(db_objs)
        self.db.flush()
        return db_objs

    def search(
        self,
        search_term: str,
        search_fields: List[str],
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        """
        Case-insensitive substring search across *search_fields*.

        Only fields that exist on the model are queried — unknown field names
        are silently skipped rather than raising AttributeError.
        """
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)

        conditions = [
            getattr(self.model, field).ilike(f"%{search_term}%")
            for field in search_fields
            if hasattr(self.model, field)
        ]

        if conditions:
            query = query.filter(or_(*conditions))

        return query.offset(skip).limit(limit).all()