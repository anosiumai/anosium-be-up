from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from api import deps
from schemas.billing import (
    Invoice, InvoiceCreate, InvoiceUpdate, InvoiceWithItems,
    Payment, PaymentCreate, PaymentSummary
)
from schemas.common import PaginatedResponse, SuccessResponse
from services.billing import BillingService
from models.user import User, UserRole
from models.tenant import Tenant
from models.billing import PaymentStatus

router = APIRouter()

@router.post("/invoices", response_model=Invoice, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_in: InvoiceCreate,
    current_user: User = Depends(deps.require_role([UserRole.RECEPTIONIST, UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Create new invoice
    
    **Required Permissions:** Receptionist, Accountant, Clinic Admin, or Super Admin
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    try:
        invoice = service.create_invoice(invoice_in)
        return invoice
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/invoices", response_model=PaginatedResponse[Invoice])
async def list_invoices(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    patient_id: Optional[int] = None,
    payment_status: Optional[PaymentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Get list of invoices with filtering
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if patient_id:
        filters["patient_id"] = patient_id
    if payment_status:
        filters["payment_status"] = payment_status
    
    result = service.get_invoices(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters=filters,
        from_date=from_date,
        to_date=to_date
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/invoices/{invoice_id}", response_model=InvoiceWithItems)
async def get_invoice(
    invoice_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get invoice with line items and payments
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    invoice = service.get_invoice_with_items(invoice_id)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice

@router.put("/invoices/{invoice_id}", response_model=Invoice)
async def update_invoice(
    invoice_id: int,
    invoice_in: InvoiceUpdate,
    current_user: User = Depends(deps.require_role([UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Update invoice
    
    **Required Permissions:** Accountant, Clinic Admin, or Super Admin
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    invoice = service.update_invoice(invoice_id, invoice_in)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice

@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Download invoice as PDF
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    pdf_bytes = service.generate_invoice_pdf(invoice_id)
    
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"
        }
    )

@router.post("/payments", response_model=Payment, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(deps.require_role([UserRole.RECEPTIONIST, UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Record payment for invoice
    
    **Required Permissions:** Receptionist, Accountant, Clinic Admin, or Super Admin
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    try:
        payment = service.create_payment(payment_in)
        return payment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/payments", response_model=PaginatedResponse[Payment])
async def list_payments(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    pagination: dict = Depends(deps.get_pagination_params),
    invoice_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Get list of payments
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    
    filters = {}
    if invoice_id:
        filters["invoice_id"] = invoice_id
    
    result = service.get_payments(
        skip=pagination["skip"],
        limit=pagination["limit"],
        filters=filters,
        from_date=from_date,
        to_date=to_date
    )
    
    return PaginatedResponse(
        items=result["items"],
        total=result["total"],
        page=pagination["page"],
        page_size=pagination["page_size"],
        total_pages=(result["total"] + pagination["page_size"] - 1) // pagination["page_size"]
    )

@router.get("/summary", response_model=PaymentSummary)
async def get_payment_summary(
    current_user: User = Depends(deps.require_role([UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Get payment summary and revenue statistics
    
    **Required Permissions:** Accountant, Clinic Admin, or Super Admin
    """
    service = BillingService(db, current_tenant.id, current_user.id)
    summary = service.get_payment_summary(from_date=from_date, to_date=to_date)
    return summary