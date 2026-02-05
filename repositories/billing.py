from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta


from models.billing import (
    Invoice, InvoiceItem, Payment, PaymentStatus, PaymentMethod,
    VisitService
)
from repositories.base import BaseRepository

class InvoiceRepository(BaseRepository[Invoice]):
    """Repository for Invoice operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Invoice, db, tenant_id, current_user_id)
    
    def get_by_invoice_number(self, invoice_number: str) -> Optional[Invoice]:
        """Get invoice by invoice number"""
        query = self.db.query(Invoice).filter(Invoice.invoice_number == invoice_number)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_with_items(self, invoice_id: int) -> Optional[Invoice]:
        """Get invoice with line items and payments"""
        query = self.db.query(Invoice).options(
            joinedload(Invoice.patient),
            joinedload(Invoice.visit),
            joinedload(Invoice.invoice_items).joinedload(InvoiceItem.service),
            joinedload(Invoice.payments)
        )
        query = query.filter(Invoice.id == invoice_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_patient(
        self,
        patient_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invoice]:
        """Get invoices for a patient"""
        query = self.db.query(Invoice).filter(Invoice.patient_id == patient_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Invoice.invoice_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_visit(self, visit_id: int) -> Optional[Invoice]:
        """Get invoice by visit ID"""
        query = self.db.query(Invoice).filter(Invoice.visit_id == visit_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_status(
        self,
        status: PaymentStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invoice]:
        """Get invoices by payment status"""
        query = self.db.query(Invoice).filter(Invoice.payment_status == status)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Invoice.invoice_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_pending_invoices(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invoice]:
        """Get pending invoices"""
        query = self.db.query(Invoice).filter(
            Invoice.payment_status.in_([
                PaymentStatus.PENDING,
                PaymentStatus.PARTIAL
            ])
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(Invoice.due_date)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_overdue_invoices(self, limit: int = 100) -> List[Invoice]:
        """Get overdue invoices"""
        today = date.today()
        
        query = self.db.query(Invoice).filter(
            and_(
                Invoice.due_date < today,
                Invoice.payment_status.in_([
                    PaymentStatus.PENDING,
                    PaymentStatus.PARTIAL
                ])
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(Invoice.due_date).limit(limit).all()
    
    def get_by_date_range(
        self,
        from_date: date,
        to_date: date,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invoice]:
        """Get invoices in date range"""
        query = self.db.query(Invoice).filter(
            and_(
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Invoice.invoice_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def generate_invoice_number(self) -> str:
        """Generate unique invoice number"""
        query = self.db.query(func.count(Invoice.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        today = date.today()
        return f"INV-{today.strftime('%Y%m%d')}-{count + 1:04d}"
    
    def calculate_totals(self, invoice_id: int) -> Dict[str, int]:
        """Calculate invoice totals"""
        invoice = self.get_with_items(invoice_id)
        if not invoice:
            return {}
        
        subtotal = sum(item.total_amount for item in invoice.invoice_items)
        discount_amount = (subtotal * invoice.discount_percentage) // 100
        tax_amount = sum(item.tax_amount for item in invoice.invoice_items)
        total_amount = subtotal - discount_amount + tax_amount
        paid_amount = sum(payment.amount for payment in invoice.payments)
        balance_amount = total_amount - paid_amount
        
        return {
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'balance_amount': balance_amount
        }
    
    def get_revenue_summary(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get revenue summary"""
        query = self.db.query(
            func.sum(Invoice.total_amount).label('total_invoiced'),
            func.sum(Invoice.paid_amount).label('total_paid'),
            func.sum(Invoice.balance_amount).label('total_pending'),
            func.count(Invoice.id).label('total_invoices')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Invoice.invoice_date >= from_date)
        
        if to_date:
            query = query.filter(Invoice.invoice_date <= to_date)
        
        result = query.first()
        
        return {
            'total_invoiced': result.total_invoiced or 0,
            'total_paid': result.total_paid or 0,
            'total_pending': result.total_pending or 0,
            'total_invoices': result.total_invoices or 0
        }
    
    def count_by_status(self) -> Dict[str, int]:
        """Count invoices by payment status"""
        query = self.db.query(
            Invoice.payment_status,
            func.count(Invoice.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(Invoice.payment_status).all()
        
        return {status.value: count for status, count in results}

class PaymentRepository(BaseRepository[Payment]):
    """Repository for Payment operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Payment, db, tenant_id, current_user_id)
    
    def get_by_payment_number(self, payment_number: str) -> Optional[Payment]:
        """Get payment by payment number"""
        query = self.db.query(Payment).filter(Payment.payment_number == payment_number)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_invoice(
        self,
        invoice_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Payment]:
        """Get payments for an invoice"""
        query = self.db.query(Payment).filter(Payment.invoice_id == invoice_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Payment.payment_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_date_range(
        self,
        from_date: datetime,
        to_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> List[Payment]:
        """Get payments in date range"""
        query = self.db.query(Payment).filter(
            and_(
                Payment.payment_date >= from_date,
                Payment.payment_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Payment.payment_date))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_today_payments(self) -> List[Payment]:
        """Get today's payments"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        query = self.db.query(Payment).filter(
            and_(
                Payment.payment_date >= today_start,
                Payment.payment_date < today_end
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(desc(Payment.payment_date)).all()
    
    def generate_payment_number(self) -> str:
        """Generate unique payment number"""
        query = self.db.query(func.count(Payment.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        today = date.today()
        return f"PAY-{today.strftime('%Y%m%d')}-{count + 1:04d}"
    
    def get_payment_summary(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get payment summary"""
        query = self.db.query(
            func.sum(Payment.amount).label('total_amount'),
            func.count(Payment.id).label('total_payments')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Payment.payment_date >= from_date)
        
        if to_date:
            query = query.filter(Payment.payment_date <= to_date)
        
        result = query.first()
        
        return {
            'total_amount': result.total_amount or 0,
            'total_payments': result.total_payments or 0
        }
    
    def count_by_method(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Count payments by payment method"""
        query = self.db.query(
            Payment.payment_method,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Payment.payment_date >= from_date)
        
        if to_date:
            query = query.filter(Payment.payment_date <= to_date)
        
        results = query.group_by(Payment.payment_method).all()
        
        return {
            method.value: {'count': count, 'total': total}
            for method, count, total in results
        }

class VisitServiceRepository(BaseRepository[VisitService]):
    """Repository for VisitService operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(VisitService, db, tenant_id, current_user_id)
    
    def get_by_visit(self, visit_id: int) -> List[VisitService]:
        """Get all services for a visit"""
        return (
            self.db.query(VisitService)
            .filter(VisitService.visit_id == visit_id)
            .all()
        )
    
    def get_total_for_visit(self, visit_id: int) -> int:
        """Calculate total cost for visit services"""
        result = (
            self.db.query(func.sum(VisitService.total_price))
            .filter(VisitService.visit_id == visit_id)
            .scalar()
        )
        
        return result or 0