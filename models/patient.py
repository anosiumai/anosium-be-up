"""
models/patient.py — aligned with actual DB schema (from column inspection).

Key differences from previous version:
  - clinic_id removed (legacy migration artefact replaced by tenant_id)
  - gender / blood_group are plain VARCHAR in DB, not PG enum types
    → use String columns; Python enum is for validation only
  - medical_history column added (JSON)
  - date_of_birth is TIMESTAMP (DateTime) not Date
  - patient_code uniqueness is per-tenant (see fix_schema.sql)
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, JSON, String, Text, func,
)
from sqlalchemy.orm import relationship

from core.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums — Python validation only; DB stores plain VARCHAR strings
# ─────────────────────────────────────────────────────────────────────────────

class Gender(str, enum.Enum):
    MALE   = "male"
    FEMALE = "female"
    OTHER  = "other"


class BloodGroup(str, enum.Enum):
    A_POSITIVE  = "A+"
    A_NEGATIVE  = "A-"
    B_POSITIVE  = "B+"
    B_NEGATIVE  = "B-"
    O_POSITIVE  = "O+"
    O_NEGATIVE  = "O-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────

class Patient(Base):
    __tablename__ = "patients"

    id        = Column(Integer, primary_key=True, index=True)

    # clinic_id removed.
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    patient_code  = Column(String,      nullable=False, index=True)
    first_name    = Column(String(100), nullable=False)
    last_name     = Column(String(100), nullable=False)

    # DB column is TIMESTAMP WITHOUT TIME ZONE
    date_of_birth = Column(DateTime, nullable=True)

    # Plain VARCHAR in DB — no PG enum type, no length risk
    gender      = Column(String(10), nullable=True)   # "male"/"female"/"other"
    blood_group = Column(String(5),  nullable=True)   # "AB+" max 3 chars

    email           = Column(String(255), nullable=True, index=True)
    phone           = Column(String(20),  nullable=False)
    alternate_phone = Column(String(20),  nullable=True)

    address     = Column(Text,        nullable=True)
    city        = Column(String(100), nullable=True)
    state       = Column(String(100), nullable=True)
    postal_code = Column(String(20),  nullable=True)

    allergies          = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    medical_history    = Column(JSON, nullable=True)  # json column in DB

    emergency_contact_name  = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(20),  nullable=True)

    registration_date = Column(DateTime, nullable=True, server_default=func.current_date())
    referred_by       = Column(String(200), nullable=True)
    is_active         = Column(Boolean,     nullable=True, default=True)
    notes             = Column(Text,        nullable=True)

    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    # Relationships
    tenant       = relationship("Tenant",       back_populates="patients",  lazy="select")
    appointments = relationship("Appointment",  back_populates="patient",   lazy="select",
                                cascade="all, delete-orphan")
    visits       = relationship("Visit",        back_populates="patient",   lazy="select",
                                cascade="all, delete-orphan")
    invoices     = relationship("Invoice",      back_populates="patient",   lazy="select",
                                cascade="all, delete-orphan")
    ai_leads         = relationship("AILead",        back_populates="patient", lazy="select")
    data_access_logs = relationship("DataAccessLog", back_populates="patient", lazy="select")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        if not self.date_of_birth:
            return 0
        today = date.today()
        dob = (self.date_of_birth.date()
               if isinstance(self.date_of_birth, datetime)
               else self.date_of_birth)
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} code={self.patient_code!r} name={self.full_name!r}>"