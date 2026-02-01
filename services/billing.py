"""
Billing Service Layer
Handles invoicing, payments, and revenue tracking
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from models.invoice import Invoice, Payment
from models.service import Service
from models.patient import Patient
from models.appointment import Appointment
from models.base import PaymentStatus
from schemas.invoice import InvoiceCreate, InvoiceLineItem, PaymentCreate
from schemas.clinic import RevenueReport


class BillingService:
    """Service for billing, invoicing, and payment operations"""
    
    @staticmethod
    def generate_invoice_number(clinic_id: int) -> str:
        """Generate unique invoice number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"INV-{clinic_id}-{timestamp}"
    
    @staticmethod
    def calculate_invoice_totals(line_items: List[InvoiceLineItem]) -> Dict[str, float]:
        """Calculate invoice totals from line items"""
        subtotal = sum(item.subtotal for item in line_items)
        tax_amount = sum(item.tax_amount for item in line_items)
        total = subtotal + tax_amount
        
        return {
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax_amount, 2),
            "total": round(total, 2)
        }
    
    @staticmethod
    def create_invoice(
        db: Session, 
        clinic_id: int, 
        invoice_data: InvoiceCreate
    ) -> Invoice:
        """
        Create a new invoice with line items
        Automatically calculates totals and taxes
        """
        # Calculate totals
        totals = BillingService.calculate_invoice_totals(invoice_data.line_items)
        
        # Apply discount
        discount_amount = invoice_data.discount_amount
        if invoice_data.discount_percentage > 0:
            discount_amount = (totals["total"] * invoice_data.discount_percentage) / 100
        
        total_amount = totals["total"] - discount_amount
        
        # Create invoice
        invoice = Invoice(
            clinic_id=clinic_id,
            patient_id=invoice_data.patient_id,
            appointment_id=invoice_data.appointment_id,
            invoice_number=BillingService.generate_invoice_number(clinic_id),
            subtotal=totals["subtotal"],
            tax_amount=totals["tax_amount"],
            discount_amount=round(discount_amount, 2),
            discount_percentage=invoice_data.discount_percentage,
            total_amount=round(total_amount, 2),
            paid_amount=0.0,
            balance_amount=round(total_amount, 2),
            payment_status=PaymentStatus.PENDING,
            payment_method=invoice_data.payment_method,
            line_items=[item.dict() for item in invoice_data.line_items],
            notes=invoice_data.notes,
            invoice_date=datetime.utcnow(),
            due_date=invoice_data.due_date or (datetime.utcnow() + timedelta(days=30))
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        return invoice
    
    @staticmethod
    def record_payment(
        db: Session,
        clinic_id: int,
        payment_data: PaymentCreate
    ) -> Optional[Payment]:
        """
        Record a payment against an invoice
        Updates invoice payment status automatically
        """
        # Get invoice
        invoice = db.query(Invoice).filter(
            and_(
                Invoice.id == payment_data.invoice_id,
                Invoice.clinic_id == clinic_id
            )
        ).first()
        
        if not invoice:
            return None
        
        # Validate payment amount
        if payment_data.amount > invoice.balance_amount:
            raise ValueError("Payment amount cannot exceed balance amount")
        
        # Create payment record
        payment = Payment(
            invoice_id=invoice.id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            transaction_id=payment_data.transaction_id,
            notes=payment_data.notes,
            payment_date=datetime.utcnow()
        )
        
        db.add(payment)
        
        # Update invoice
        invoice.paid_amount += payment_data.amount
        invoice.balance_amount -= payment_data.amount
        invoice.payment_method = payment_data.payment_method
        
        # Update payment status
        if invoice.balance_amount <= 0:
            invoice.payment_status = PaymentStatus.PAID
            invoice.paid_date = datetime.utcnow()
        elif invoice.paid_amount > 0:
            invoice.payment_status = PaymentStatus.PARTIAL
        
        invoice.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(payment)
        
        return payment
    
    @staticmethod
    def get_invoice_by_id(db: Session, clinic_id: int, invoice_id: int) -> Optional[Invoice]:
        """Get invoice by ID"""
        return db.query(Invoice).filter(
            and_(
                Invoice.id == invoice_id,
                Invoice.clinic_id == clinic_id
            )
        ).first()
    
    @staticmethod
    def get_invoice_by_number(db: Session, clinic_id: int, invoice_number: str) -> Optional[Invoice]:
        """Get invoice by number"""
        return db.query(Invoice).filter(
            and_(
                Invoice.invoice_number == invoice_number,
                Invoice.clinic_id == clinic_id
            )
        ).first()
    
    @staticmethod
    def list_invoices(
        db: Session,
        clinic_id: int,
        patient_id: Optional[int] = None,
        status: Optional[PaymentStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invoice]:
        """List invoices with filters"""
        query = db.query(Invoice).filter(Invoice.clinic_id == clinic_id)
        
        if patient_id:
            query = query.filter(Invoice.patient_id == patient_id)
        
        if status:
            query = query.filter(Invoice.payment_status == status)
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= from_date)
        
        if to_date:
            query = query.filter(Invoice.invoice_date <= to_date)
        
        return query.order_by(Invoice.invoice_date.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_pending_invoices(db: Session, clinic_id: int) -> List[Invoice]:
        """Get all pending invoices for a clinic"""
        return db.query(Invoice).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.balance_amount > 0
            )
        ).order_by(Invoice.due_date).all()
    
    @staticmethod
    def get_overdue_invoices(db: Session, clinic_id: int) -> List[Invoice]:
        """Get overdue invoices"""
        return db.query(Invoice).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.balance_amount > 0,
                Invoice.due_date < datetime.utcnow()
            )
        ).order_by(Invoice.due_date).all()
    
    @staticmethod
    def get_patient_invoices(
        db: Session,
        clinic_id: int,
        patient_id: int
    ) -> List[Invoice]:
        """Get all invoices for a patient"""
        return db.query(Invoice).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.patient_id == patient_id
            )
        ).order_by(Invoice.invoice_date.desc()).all()
    
    @staticmethod
    def create_service(
        db: Session,
        clinic_id: int,
        name: str,
        price: float,
        description: Optional[str] = None,
        tax_percentage: float = 0.0,
        category: Optional[str] = None,
        is_package: bool = False
    ) -> Service:
        """Create a new service/item"""
        service = Service(
            clinic_id=clinic_id,
            name=name,
            description=description,
            price=price,
            tax_percentage=tax_percentage,
            category=category,
            is_package=is_package
        )
        
        db.add(service)
        db.commit()
        db.refresh(service)
        
        return service
    
    @staticmethod
    def list_services(
        db: Session,
        clinic_id: int,
        category: Optional[str] = None,
        is_active: bool = True
    ) -> List[Service]:
        """List all services for a clinic"""
        query = db.query(Service).filter(
            and_(
                Service.clinic_id == clinic_id,
                Service.is_active == is_active
            )
        )
        
        if category:
            query = query.filter(Service.category == category)
        
        return query.order_by(Service.name).all()
    
    @staticmethod
    def get_revenue_report(
        db: Session,
        clinic_id: int,
        from_date: datetime,
        to_date: datetime
    ) -> RevenueReport:
        """
        Generate comprehensive revenue report for a period
        """
        # Total revenue
        total_revenue = db.query(func.sum(Invoice.paid_amount)).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date
            )
        ).scalar() or 0.0
        
        # Total invoices
        total_invoices = db.query(func.count(Invoice.id)).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date
            )
        ).scalar()
        
        # Paid invoices
        paid_invoices = db.query(func.count(Invoice.id)).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date,
                Invoice.payment_status == PaymentStatus.PAID
            )
        ).scalar()
        
        # Pending amount
        pending_amount = db.query(func.sum(Invoice.balance_amount)).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date,
                Invoice.balance_amount > 0
            )
        ).scalar() or 0.0
        
        # Payment methods breakdown
        payment_methods = db.query(
            Payment.payment_method,
            func.sum(Payment.amount)
        ).join(Invoice).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Payment.payment_date >= from_date,
                Payment.payment_date <= to_date
            )
        ).group_by(Payment.payment_method).all()
        
        payment_methods_dict = {method: float(amount) for method, amount in payment_methods}
        
        # Revenue by service (from line items)
        invoices = db.query(Invoice).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date
            )
        ).all()
        
        service_revenue = {}
        for invoice in invoices:
            for item in invoice.line_items:
                service_name = item.get("name", "Unknown")
                if service_name in service_revenue:
                    service_revenue[service_name] += item.get("total", 0)
                else:
                    service_revenue[service_name] = item.get("total", 0)
        
        revenue_by_service = [
            {"service": name, "revenue": round(amount, 2)}
            for name, amount in sorted(service_revenue.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Daily revenue
        daily_revenue = db.query(
            func.date(Invoice.invoice_date).label('date'),
            func.sum(Invoice.paid_amount).label('revenue')
        ).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date
            )
        ).group_by(func.date(Invoice.invoice_date)).all()
        
        daily_revenue_list = [
            {"date": str(date), "revenue": float(revenue or 0)}
            for date, revenue in daily_revenue
        ]
        
        period_str = f"{from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"
        
        return RevenueReport(
            period=period_str,
            total_revenue=round(total_revenue, 2),
            total_invoices=total_invoices,
            paid_invoices=paid_invoices,
            pending_amount=round(pending_amount, 2),
            payment_methods=payment_methods_dict,
            revenue_by_service=revenue_by_service[:10],  # Top 10
            daily_revenue=daily_revenue_list
        )
    
    @staticmethod
    def cancel_invoice(db: Session, clinic_id: int, invoice_id: int, reason: str = None) -> Optional[Invoice]:
        """Cancel an invoice"""
        invoice = db.query(Invoice).filter(
            and_(
                Invoice.id == invoice_id,
                Invoice.clinic_id == clinic_id
            )
        ).first()
        
        if not invoice:
            return None
        
        if invoice.paid_amount > 0:
            raise ValueError("Cannot cancel invoice with payments")
        
        invoice.payment_status = PaymentStatus.CANCELLED
        invoice.notes = f"{invoice.notes or ''}\n\nCANCELLED: {reason or 'No reason provided'}"
        invoice.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(invoice)
        
        return invoice
    
    @staticmethod
    def apply_discount_to_invoice(
        db: Session,
        clinic_id: int,
        invoice_id: int,
        discount_percentage: float = 0.0,
        discount_amount: float = 0.0
    ) -> Optional[Invoice]:
        """Apply discount to existing invoice"""
        invoice = db.query(Invoice).filter(
            and_(
                Invoice.id == invoice_id,
                Invoice.clinic_id == clinic_id
            )
        ).first()
        
        if not invoice:
            return None
        
        # Calculate new discount
        base_total = invoice.subtotal + invoice.tax_amount
        
        if discount_percentage > 0:
            discount_amount = (base_total * discount_percentage) / 100
        
        invoice.discount_percentage = discount_percentage
        invoice.discount_amount = round(discount_amount, 2)
        invoice.total_amount = round(base_total - discount_amount, 2)
        invoice.balance_amount = invoice.total_amount - invoice.paid_amount
        
        # Update status if fully paid
        if invoice.balance_amount <= 0:
            invoice.payment_status = PaymentStatus.PAID
        elif invoice.paid_amount > 0:
            invoice.payment_status = PaymentStatus.PARTIAL
        
        invoice.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(invoice)
        
        return invoice