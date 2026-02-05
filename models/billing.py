"""
Billing Models
Invoices, payments, and financial transactions
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum


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


class Invoice(Base):
    """
    Patient invoices with line items
    """
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id", ondelete="SET NULL"), unique=True)
    
    # Invoice Details
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    invoice_date = Column(Date, nullable=False, server_default=func.current_date())
    due_date = Column(Date)
    
    # Amounts (in cents/paise)
    subtotal = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, default=0)
    discount_percentage = Column(Integer, default=0)
    discount_reason = Column(String(200))
    tax_amount = Column(Integer, default=0)
    total_amount = Column(Integer, nullable=False)
    paid_amount = Column(Integer, default=0)
    balance_amount = Column(Integer, default=0)
    
    # Status
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, index=True)
    
    # Notes
    notes = Column(Text)
    terms_conditions = Column(Text)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # Relationships
    tenant = relationship("Tenant", viewonly=True)
    patient = relationship("Patient", back_populates="invoices")
    visit = relationship("Visit", back_populates="invoice", uselist=False)
    invoice_items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """
    Line items in an invoice
    """
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"))
    
    description = Column(String(500), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Integer, nullable=False)
    tax_percentage = Column(Integer, default=0)
    tax_amount = Column(Integer, default=0)
    total_amount = Column(Integer, nullable=False)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="invoice_items")
    service = relationship("Service", viewonly=True)


class Payment(Base):
    """
    Payment transactions
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Payment Details
    payment_number = Column(String(50), unique=True, nullable=False, index=True)
    payment_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    amount = Column(Integer, nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    
    # Transaction Details
    transaction_id = Column(String(200))  # External transaction ID
    reference_number = Column(String(200))
    
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # Relationships
    tenant = relationship("Tenant", viewonly=True)
    invoice = relationship("Invoice", back_populates="payments")


class VisitService(Base):
    """
    Services rendered during a visit (for billing)
    """
    __tablename__ = "visit_services"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    
    quantity = Column(Integer, default=1)
    unit_price = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    visit = relationship("Visit", back_populates="visit_services")
    service = relationship("Service", viewonly=True)