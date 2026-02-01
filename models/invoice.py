from .base import Base, PaymentStatus
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index, JSON, Enum as SQLEnum
from datetime import datetime

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # Amounts
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    discount_percentage = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0)
    balance_amount = Column(Float, nullable=False)
    
    # Payment
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(String(50))
    
    # Items
    line_items = Column(JSON, default=[])  # [{service_id, name, quantity, price, tax}]
    
    # Notes
    notes = Column(Text)
    
    # Dates
    invoice_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    paid_date = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_invoice_clinic_date', 'clinic_id', 'invoice_date'),
        Index('idx_invoice_status', 'payment_status', 'clinic_id'),
    )


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False)  # cash, card, upi, insurance
    transaction_id = Column(String(100))
    
    notes = Column(Text)
    payment_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_payment_invoice', 'invoice_id', 'payment_date'),
    )