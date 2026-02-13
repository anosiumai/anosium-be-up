"""
Billing Models
Invoices, payments, and financial transactions
Production-grade architecture.
"""

import enum

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Date,
    func,
    Index,
    CheckConstraint
)

from sqlalchemy.orm import relationship
from core.database import Base


# =========================================================
# ENUMS
# =========================================================

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    INSURANCE = "insurance"
    WALLET = "wallet"


# =========================================================
# INVOICE
# =========================================================

class Invoice(Base):
    """
    Patient invoices with line items.
    """

    __tablename__ = "invoices"

    id = Column(BigInteger, primary_key=True)

    tenant_id = Column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        BigInteger,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    visit_id = Column(
        BigInteger,
        ForeignKey("visits.id", ondelete="SET NULL"),
        unique=True,
        index=True
    )

    # Invoice Details
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    invoice_date = Column(
        Date,
        nullable=False,
        server_default=func.current_date()
    )

    due_date = Column(Date)

    # Monetary values stored in smallest currency unit (paise / cents)
    subtotal = Column(BigInteger, nullable=False, default=0)

    discount_amount = Column(BigInteger, default=0)
    discount_percentage = Column(Integer, default=0)

    discount_reason = Column(Text)  # NEW
    tax_amount = Column(BigInteger, default=0)

    total_amount = Column(BigInteger, nullable=False)

    paid_amount = Column(BigInteger, default=0)
    balance_amount = Column(BigInteger, default=0)

    payment_status = Column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        index=True
    )

    notes = Column(Text)
    terms_conditions = Column(Text)  # NEW

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )

    # ================= RELATIONSHIPS =================

    tenant = relationship("Tenant", viewonly=True)

    patient = relationship(
        "Patient",
        back_populates="invoices"
    )

    visit = relationship(
        "Visit",
        back_populates="invoice",
        uselist=False
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by],
        viewonly=True
    )

    invoice_items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    payments = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    __table_args__ = (

        # Prevent negative money bugs (VERY common production issue)
        CheckConstraint("subtotal >= 0"),
        CheckConstraint("discount_amount >= 0"),
        CheckConstraint("tax_amount >= 0"),
        CheckConstraint("total_amount >= 0"),
        CheckConstraint("paid_amount >= 0"),
        CheckConstraint("balance_amount >= 0"),

        Index("ix_invoice_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_invoice_status", "payment_status"),
    )


# =========================================================
# INVOICE ITEMS
# =========================================================

class InvoiceItem(Base):
    """
    Line items inside an invoice.
    """

    __tablename__ = "invoice_items"

    id = Column(BigInteger, primary_key=True)

    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    service_id = Column(
        BigInteger,
        ForeignKey("services.id", ondelete="SET NULL"),
        index=True
    )

    description = Column(String(500), nullable=False)

    quantity = Column(Integer, default=1)
    unit_price = Column(BigInteger, nullable=False)

    tax_percentage = Column(Integer, default=0)
    tax_amount = Column(BigInteger, default=0)

    total_amount = Column(BigInteger, nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="invoice_items")
    service = relationship("Service", viewonly=True)

    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price >= 0"),
        CheckConstraint("tax_amount >= 0"),
        CheckConstraint("total_amount >= 0"),

        Index("ix_invoice_items_invoice", "invoice_id"),
    )


# =========================================================
# PAYMENTS
# =========================================================

class Payment(Base):
    """
    Payment transactions against invoices.
    """

    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True)

    tenant_id = Column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    payment_number = Column(String(50), unique=True, nullable=False, index=True)

    payment_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    amount = Column(BigInteger, nullable=False)

    payment_method = Column(
        SQLEnum(PaymentMethod),
        nullable=False
    )

    transaction_id = Column(String(200))
    reference_number = Column(String(200))

    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    created_by = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Relationships
    tenant = relationship("Tenant", viewonly=True)

    invoice = relationship(
        "Invoice",
        back_populates="payments"
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by],
        viewonly=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0"),
        Index("ix_payment_invoice", "invoice_id"),
    )


# =========================================================
# VISIT SERVICES
# =========================================================

class VisitService(Base):
    """
    Services rendered during a visit.
    Often used to auto-generate invoice items.
    """

    __tablename__ = "visit_services"

    id = Column(BigInteger, primary_key=True)

    visit_id = Column(
        BigInteger,
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    service_id = Column(
        BigInteger,
        ForeignKey("services.id", ondelete="SET NULL"),
        index=True
    )

    quantity = Column(Integer, default=1)
    unit_price = Column(BigInteger, nullable=False)
    total_price = Column(BigInteger, nullable=False)

    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    visit = relationship("Visit", back_populates="visit_services")
    service = relationship("Service", viewonly=True)

    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price >= 0"),
        CheckConstraint("total_price >= 0"),

        Index("ix_visit_services_visit", "visit_id"),
    )
