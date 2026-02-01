from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

class InvoiceLineItem(BaseModel):
    """Individual line item in an invoice"""
    service_id: Optional[int] = None
    name: str = Field(..., min_length=1)
    quantity: int = Field(ge=1, default=1)
    price: float = Field(gt=0)
    tax_percentage: float = Field(ge=0, default=0.0)
    discount_percentage: float = Field(ge=0, le=100, default=0.0)
    
    @property
    def subtotal(self) -> float:
        return self.price * self.quantity
    
    @property
    def discount_amount(self) -> float:
        return (self.subtotal * self.discount_percentage) / 100
    
    @property
    def subtotal_after_discount(self) -> float:
        return self.subtotal - self.discount_amount
    
    @property
    def tax_amount(self) -> float:
        return (self.subtotal_after_discount * self.tax_percentage) / 100
    
    @property
    def total(self) -> float:
        return self.subtotal_after_discount + self.tax_amount


class InvoiceCreate(BaseModel):
    """Schema for creating a new invoice"""
    patient_id: int = Field(..., gt=0)
    appointment_id: Optional[int] = None
    line_items: List[InvoiceLineItem] = Field(..., min_length=1)
    discount_percentage: float = Field(ge=0, le=100, default=0.0)
    discount_amount: float = Field(ge=0, default=0.0)
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": 1,
                "line_items": [
                    {
                        "service_id": 1,
                        "name": "General Consultation",
                        "quantity": 1,
                        "price": 100.00,
                        "tax_percentage": 10.0
                    }
                ],
                "discount_percentage": 5.0,
                "notes": "Regular checkup"
            }
        }


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice"""
    notes: Optional[str] = None
    due_date: Optional[datetime] = None
    payment_method: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Response schema for invoice"""
    id: int
    clinic_id: int
    patient_id: int
    appointment_id: Optional[int]
    invoice_number: str
    
    # Financial details
    subtotal: float
    tax_amount: float
    discount_amount: float
    discount_percentage: float
    total_amount: float
    paid_amount: float
    balance_amount: float
    
    # Status and payment
    payment_status: str
    payment_method: Optional[str]
    
    # Line items
    line_items: List[Dict[str, Any]]
    
    # Additional info
    notes: Optional[str]
    
    # Dates
    invoice_date: datetime
    due_date: Optional[datetime]
    paid_date: Optional[datetime]
    cancelled_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Patient info (optional, can be included via joins)
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None

    class Config:
        from_attributes = True


class InvoiceSummary(BaseModel):
    """Simplified invoice summary for lists"""
    id: int
    invoice_number: str
    patient_id: int
    patient_name: str
    total_amount: float
    paid_amount: float
    balance_amount: float
    payment_status: str
    invoice_date: datetime
    due_date: Optional[datetime]
    
    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    """Schema for recording a payment"""
    invoice_id: int = Field(..., gt=0)
    amount: float = Field(gt=0)
    payment_method: str = Field(..., min_length=1)
    transaction_id: Optional[str] = None
    notes: Optional[str] = None
    payment_date: Optional[datetime] = None


class PaymentResponse(BaseModel):
    """Response schema for payment"""
    id: int
    invoice_id: int
    clinic_id: int
    amount: float
    payment_method: str
    transaction_id: Optional[str]
    notes: Optional[str]
    payment_date: datetime
    created_at: datetime
    created_by: Optional[int] = None
    
    # Optional invoice info
    invoice_number: Optional[str] = None
    patient_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentSummary(BaseModel):
    """Summary of payments"""
    total_amount: float
    payment_count: int
    payment_methods: Dict[str, float]
    
    class Config:
        from_attributes = True