from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List, TYPE_CHECKING
from datetime import date, datetime
from models.billing import PaymentStatus, PaymentMethod

if TYPE_CHECKING:
    from schemas.visit import Visit
    from schemas.patient import Patient

class InvoiceItemCreate(BaseModel):
    """Create invoice item"""
    service_id: Optional[int] = None
    description: str = Field(..., min_length=2, max_length=500)
    quantity: int = Field(default=1, ge=1)
    unit_price: int = Field(..., ge=0)
    tax_percentage: int = Field(default=0, ge=0, le=100)

class InvoiceItem(BaseModel):
    """Invoice line item"""
    id: int
    service_id: Optional[int]
    description: str
    quantity: int
    unit_price: int
    tax_percentage: int
    tax_amount: int
    total_amount: int
    
    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    """Base invoice schema"""
    invoice_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    discount_percentage: int = Field(default=0, ge=0, le=100)
    discount_reason: Optional[str] = None
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @validator('due_date')
    def validate_due_date(cls, v, values):
        invoice_date = values.get('invoice_date')
        if v and invoice_date and v < invoice_date:
            raise ValueError('Due date cannot be before invoice date')
        return v

class InvoiceCreate(InvoiceBase):
    """Create invoice schema"""
    patient_id: int
    visit_id: Optional[int] = None
    items: List[InvoiceItemCreate] = Field(..., min_items=1)

class InvoiceUpdate(BaseModel):
    """Update invoice schema"""
    due_date: Optional[date] = None
    discount_percentage: Optional[int] = Field(None, ge=0, le=100)
    discount_reason: Optional[str] = None
    notes: Optional[str] = None
    payment_status: Optional[PaymentStatus] = None

class InvoiceInDB(InvoiceBase):
    """Invoice from database"""
    id: int
    tenant_id: int
    patient_id: int
    visit_id: Optional[int]
    invoice_number: str
    subtotal: int
    discount_amount: int
    tax_amount: int
    total_amount: int
    paid_amount: int
    balance_amount: int
    payment_status: PaymentStatus
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[int]

class Invoice(InvoiceInDB):
    """Public invoice schema"""
    patient: 'Patient'
    visit: Optional['Visit'] = None

class InvoiceWithItems(Invoice):
    """Invoice with line items"""
    items: List[InvoiceItem] = []
    payments: List['Payment'] = []

class PaymentBase(BaseModel):
    """Base payment schema"""
    amount: int = Field(..., gt=0)
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class PaymentCreate(PaymentBase):
    """Create payment schema"""
    invoice_id: int

class PaymentInDB(PaymentBase):
    """Payment from database"""
    id: int
    tenant_id: int
    invoice_id: int
    payment_number: str
    payment_date: datetime
    created_at: datetime
    created_by: Optional[int]

class Payment(PaymentInDB):
    """Public payment schema"""
    invoice: Optional['Invoice'] = None

class PaymentSummary(BaseModel):
    """Payment summary for dashboard"""
    total_revenue: int = 0
    paid_amount: int = 0
    pending_amount: int = 0
    today_revenue: int = 0
    this_month_revenue: int = 0
    payment_methods_breakdown: Dict[str, int] = {}