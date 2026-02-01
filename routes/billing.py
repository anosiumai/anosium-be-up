"""
FastAPI Routes for Billing & Invoicing
Handles invoice creation, payments, and revenue tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from core.database import get_db
from schemas.invoice import InvoiceCreate, InvoiceResponse, PaymentCreate, PaymentResponse
from schemas.service import ServiceCreate, ServiceResponse
from schemas.clinic import RevenueReport
from schemas.common import MessageResponse
from services.billing import BillingService
from services.multi_clinic import MultiClinicService
from core.security import get_current_user, require_clinic_access
from models.user import User
from models.base import UserRole, PaymentStatus
from models.patient import Patient

router = APIRouter(prefix="/api/billing", tags=["Billing"])


# ==================== SERVICES ====================
@router.post("/{clinic_id}/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    clinic_id: int,
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Create a new service/item"""
    # Check access
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check if clinic has billing feature
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not MultiClinicService.check_feature_access(clinic, "advanced_billing"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Advanced billing not available in current subscription"
        )
    
    service = BillingService.create_service(
        db, clinic_id,
        service_data.name,
        service_data.price,
        service_data.description,
        service_data.tax_percentage,
        service_data.category,
        service_data.is_package
    )
    return service


@router.get("/{clinic_id}/services", response_model=List[ServiceResponse])
async def list_services(
    clinic_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """List all services for a clinic"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    services = BillingService.list_services(db, clinic_id, category)
    return services


# ==================== INVOICES ====================
@router.post("/{clinic_id}/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    clinic_id: int,
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """
    Create a new invoice
    Automatically calculates totals, taxes, and discounts
    """
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Validate patient belongs to clinic
    patient = db.query(Patient).filter(
        Patient.id == invoice_data.patient_id,
        Patient.clinic_id == clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found in this clinic"
        )
    
    invoice = BillingService.create_invoice(db, clinic_id, invoice_data)
    return invoice


@router.get("/{clinic_id}/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    clinic_id: int,
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get invoice by ID"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoice = BillingService.get_invoice_by_id(db, clinic_id, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.get("/{clinic_id}/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    clinic_id: int,
    patient_id: Optional[int] = None,
    status: Optional[PaymentStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """List invoices with filters"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoices = BillingService.list_invoices(
        db, clinic_id, patient_id, status, from_date, to_date, skip, limit
    )
    return invoices


@router.get("/{clinic_id}/invoices/pending/all", response_model=List[InvoiceResponse])
async def get_pending_invoices(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get all pending invoices"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoices = BillingService.get_pending_invoices(db, clinic_id)
    return invoices


@router.get("/{clinic_id}/invoices/overdue/all", response_model=List[InvoiceResponse])
async def get_overdue_invoices(
    clinic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get all overdue invoices"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoices = BillingService.get_overdue_invoices(db, clinic_id)
    return invoices


@router.post("/{clinic_id}/invoices/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    clinic_id: int,
    invoice_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Cancel an invoice"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    try:
        invoice = BillingService.cancel_invoice(db, clinic_id, invoice_id, reason)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        return invoice
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{clinic_id}/invoices/{invoice_id}/discount", response_model=InvoiceResponse)
async def apply_discount(
    clinic_id: int,
    invoice_id: int,
    discount_percentage: float = 0.0,
    discount_amount: float = 0.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Apply discount to invoice"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoice = BillingService.apply_discount_to_invoice(
        db, clinic_id, invoice_id, discount_percentage, discount_amount
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    return invoice


# ==================== PAYMENTS ====================
@router.post("/{clinic_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    clinic_id: int,
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """
    Record a payment against an invoice
    Automatically updates invoice status
    """
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    try:
        payment = BillingService.record_payment(db, clinic_id, payment_data)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        return payment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== REPORTS ====================
@router.get("/{clinic_id}/reports/revenue", response_model=RevenueReport)
async def get_revenue_report(
    clinic_id: int,
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """
    Generate comprehensive revenue report
    Defaults to current month if dates not provided
    """
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Check analytics feature
    clinic = MultiClinicService.get_clinic_by_id(db, clinic_id)
    if not MultiClinicService.check_feature_access(clinic, "analytics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analytics not available in current subscription"
        )
    
    # Default to current month
    if not from_date:
        from_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not to_date:
        to_date = datetime.utcnow()
    
    report = BillingService.get_revenue_report(db, clinic_id, from_date, to_date)
    return report


@router.get("/{clinic_id}/patients/{patient_id}/invoices", response_model=List[InvoiceResponse])
async def get_patient_invoices(
    clinic_id: int,
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinic_access)
):
    """Get all invoices for a specific patient"""
    if current_user.clinic_id != clinic_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    invoices = BillingService.get_patient_invoices(db, clinic_id, patient_id)
    return invoices