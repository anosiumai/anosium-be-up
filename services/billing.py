from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.billing import (
    Invoice,
    InvoiceItem,
    Payment,
    PaymentStatus,
    PaymentMethod,
    VisitService as VisitServiceModel,
)
from models.patient import Patient
from models.visit import Visit
from schemas.billing import (
    InvoiceCreate,
    InvoiceUpdate,
    PaymentCreate,
    PaymentSummary,
)
from repositories.billing import (
    InvoiceRepository,
    PaymentRepository,
    VisitServiceRepository,
)


class BillingService:
    """Service layer for Invoice & Payment business logic."""

    # default number of days until an invoice is due
    DEFAULT_DUE_DAYS: int = 30

    def __init__(
        self,
        db: Session,
        tenant_id: int,
        current_user_id: Optional[int] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id

        self.invoice_repo = InvoiceRepository(db, tenant_id, current_user_id)
        self.payment_repo = PaymentRepository(db, tenant_id, current_user_id)
        self.visit_service_repo = VisitServiceRepository(db, tenant_id, current_user_id)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _normalize_status(self, status: Optional[str]) -> Optional[PaymentStatus]:
        """Map frontend status strings to backend PaymentStatus enum."""
        if not status:
            return None
        
        mapping = {
            # Frontend → Backend
            'PENDING': PaymentStatus.PENDING,
            'PARTIALLY_PAID': PaymentStatus.PARTIAL,  # Critical mapping!
            'PAID': PaymentStatus.PAID,
            'CANCELLED': PaymentStatus.CANCELLED,
            'DRAFT': PaymentStatus.PENDING,  # Draft treated as pending backend-side
            'OVERDUE': PaymentStatus.PENDING,  # Overdue is a UI concept, not a payment state
        }
        return mapping.get(status.upper())
    
    def _get_patient(self, patient_id: int) -> Patient:
        """Resolve patient; raise if missing or wrong tenant."""
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.tenant_id == self.tenant_id)
            .first()
        )
        if not patient:
            raise ValueError(f"Patient with id {patient_id} not found")
        return patient

    def _get_visit(self, visit_id: int) -> Visit:
        """Resolve visit; raise if missing or wrong tenant."""
        visit = (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.tenant_id == self.tenant_id)
            .first()
        )
        if not visit:
            raise ValueError(f"Visit with id {visit_id} not found")
        return visit

    @staticmethod
    def _compute_item_totals(unit_price: int, quantity: int, tax_percentage: int) -> Dict[str, int]:
        """
        Return (line_total_before_tax, tax_amount, total_amount) for a single
        invoice line.  All values are in the smallest currency unit (paise/cents).
        """
        line_subtotal = unit_price * quantity
        tax_amount = (line_subtotal * tax_percentage) // 100
        total_amount = line_subtotal + tax_amount
        return {
            "line_subtotal": line_subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
        }

    def _recalculate_invoice_totals(self, invoice: Invoice) -> None:
        """
        Re-derive subtotal / tax / discount / balance on the invoice row from
        its current line items and payments.  Call before every commit that may
        have changed items or the discount.
        """
        subtotal = sum(item.total_amount - item.tax_amount for item in invoice.invoice_items)
        tax_amount = sum(item.tax_amount for item in invoice.invoice_items)
        discount_amount = (subtotal * invoice.discount_percentage) // 100
        total_amount = subtotal - discount_amount + tax_amount
        paid_amount = sum(p.amount for p in invoice.payments)
        balance_amount = total_amount - paid_amount

        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.discount_amount = discount_amount
        invoice.total_amount = total_amount
        invoice.paid_amount = paid_amount
        invoice.balance_amount = balance_amount

    def _resolve_payment_status(self, invoice: Invoice) -> PaymentStatus:
        """Derive the correct PaymentStatus from current amounts."""
        if invoice.balance_amount <= 0:
            return PaymentStatus.PAID
        if invoice.paid_amount > 0:
            return PaymentStatus.PARTIAL
        return PaymentStatus.PENDING

    # ------------------------------------------------------------------
    # Invoice CRUD
    # ------------------------------------------------------------------

    def create_invoice(self, invoice_in: InvoiceCreate) -> Invoice:
        """
        Create an invoice with validated line items.

        Validations
        -----------
        * Patient exists within the tenant.
        * Visit (optional) exists, belongs to tenant, and does not already have
          an invoice (the FK is ``unique``).
        * At least one line item is present (enforced by the schema, but
          double-checked here).
        * ``due_date`` defaults to invoice_date + DEFAULT_DUE_DAYS when omitted.
        """
        # --- FK validation ------------------------------------------------
        self._get_patient(invoice_in.patient_id)
        

        if invoice_in.visit_id:
            visit = self._get_visit(invoice_in.visit_id)
            existing_invoice = self.invoice_repo.get_by_visit(visit.id)
            if existing_invoice:
                raise ValueError(
                    f"Visit {visit.id} already has invoice {existing_invoice.invoice_number}"
                )

        if not invoice_in.items:
            raise ValueError("Invoice must contain at least one line item")

        # --- defaults -----------------------------------------------------
        invoice_date = invoice_in.invoice_date or date.today()
        due_date = invoice_in.due_date or (invoice_date + timedelta(days=self.DEFAULT_DUE_DAYS))

        invoice_number = self.invoice_repo.generate_invoice_number()

        # --- build ORM invoice (amounts filled after items are created) ----
        invoice = Invoice(
            tenant_id=self.tenant_id,
            # clinic_id=self.tenant_id,
            patient_id=invoice_in.patient_id,
            visit_id=invoice_in.visit_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            discount_percentage=invoice_in.discount_percentage,
            discount_reason=invoice_in.discount_reason,
            notes=invoice_in.notes,
            terms_conditions=invoice_in.terms_conditions,
            # placeholder – will be overwritten by _recalculate_invoice_totals
            subtotal=0,
            total_amount=0,
            created_by=self.current_user_id,
        )
        self.db.add(invoice)
        self.db.flush()  # get invoice.id without full commit

        # --- build line items ---------------------------------------------
        for item_in in invoice_in.items:
            computed = self._compute_item_totals(
                item_in.unit_price, item_in.quantity, item_in.tax_percentage
            )
            item = InvoiceItem(
                invoice_id=invoice.id,
                service_id=item_in.service_id,
                description=item_in.description,
                quantity=item_in.quantity,
                unit_price=item_in.unit_price,
                tax_percentage=item_in.tax_percentage,
                tax_amount=computed["tax_amount"],
                total_amount=computed["total_amount"],
            )
            self.db.add(item)

        self.db.flush()  # persist items so the relationship is populated

        # --- derive invoice-level totals ----------------------------------
        self._recalculate_invoice_totals(invoice)
        invoice.payment_status = self._resolve_payment_status(invoice)

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get_invoice_with_items(self, invoice_id: int) -> Optional[Invoice]:
        """Fetch a single invoice with items + payments eager-loaded."""
        return self.invoice_repo.get_with_items(invoice_id)

    def get_invoices(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Paginated invoice listing.

        ``filters`` may contain ``patient_id`` and/or ``payment_status``.
        Returns ``{"items": [...], "total": int}``.
        """
        filters = filters or {}

        query = self.db.query(Invoice).filter(Invoice.tenant_id == self.tenant_id)

        if "patient_id" in filters:
            query = query.filter(Invoice.patient_id == filters["patient_id"])

        if "payment_status" in filters:
            query = query.filter(Invoice.payment_status == filters["payment_status"])

        if from_date:
            query = query.filter(Invoice.invoice_date >= from_date)

        if to_date:
            query = query.filter(Invoice.invoice_date <= to_date)

        total = query.count()

        items = (
            query.order_by(desc(Invoice.invoice_date))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total}

    def update_invoice(self, invoice_id: int, invoice_in: InvoiceUpdate) -> Optional[Invoice]:
        invoice = self.invoice_repo.get_with_items(invoice_id)
        if not invoice:
            return None

        # --- guard locked statuses ----------------------------------------
        if invoice.payment_status in (PaymentStatus.PAID, PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
            raise ValueError(
                f"Invoice {invoice.invoice_number} is locked in status "
                f"'{invoice.payment_status.value}' and cannot be updated"
            )

        update_data = invoice_in.model_dump(exclude_unset=True)

        # --- Handle status field (frontend compatibility) ------------------
        # Accept either 'status' (frontend) or 'payment_status' (backend)
        raw_status = update_data.pop("status", None) or update_data.pop("payment_status", None)
        normalized_status = self._normalize_status(raw_status) if raw_status else None

        # --- Apply scalar fields ------------------------------------------
        for key, value in update_data.items():
            setattr(invoice, key, value)

        # --- Recalculate totals -------------------------------------------
        self._recalculate_invoice_totals(invoice)

        # --- Handle status update logic -----------------------------------
        if normalized_status:
            # Allow manual updates for non-final statuses
            if normalized_status in (PaymentStatus.PENDING, PaymentStatus.PARTIAL, PaymentStatus.CANCELLED):
                invoice.payment_status = normalized_status
            elif normalized_status == PaymentStatus.PAID:
                # PAID should only be set via payment, not manual update
                raise ValueError(
                    "Status 'PAID' cannot be set manually. "
                    "Please record a payment for the full balance instead."
                )
            else:
                # Fallback to auto-derived status
                invoice.payment_status = self._resolve_payment_status(invoice)
        else:
            # Auto-derive status from amounts
            invoice.payment_status = self._resolve_payment_status(invoice)

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    # ------------------------------------------------------------------
    # Payment
    # ------------------------------------------------------------------

    def create_payment(self, payment_in: PaymentCreate) -> Payment:
        """
        Record a payment against an invoice.

        Validations
        -----------
        * Invoice exists within the tenant.
        * Invoice is not already PAID, CANCELLED, or REFUNDED.
        * Payment amount does not exceed the current balance.

        Side-effects
        ------------
        * Updates ``paid_amount`` / ``balance_amount`` on the invoice.
        * Transitions ``payment_status`` to PARTIAL or PAID as appropriate.
        """
        invoice = self.invoice_repo.get_with_items(payment_in.invoice_id)
        if not invoice:
            raise ValueError(f"Invoice with id {payment_in.invoice_id} not found")

        if invoice.payment_status in (PaymentStatus.PAID, PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
            raise ValueError(
                f"Invoice {invoice.invoice_number} is in status "
                f"'{invoice.payment_status.value}' — no further payments accepted"
            )

        if payment_in.amount <= 0:
            raise ValueError("Payment amount must be greater than zero")

        if payment_in.amount > invoice.balance_amount:
            raise ValueError(
                f"Payment amount ({payment_in.amount}) exceeds outstanding "
                f"balance ({invoice.balance_amount}) on invoice {invoice.invoice_number}"
            )

        # --- persist payment ----------------------------------------------
        payment_number = self.payment_repo.generate_payment_number()

        payment = Payment(
            tenant_id=self.tenant_id,
            invoice_id=invoice.id,
            payment_number=payment_number,
            payment_date=datetime.utcnow(),
            amount=payment_in.amount,
            payment_method=payment_in.payment_method,
            transaction_id=payment_in.transaction_id,
            reference_number=payment_in.reference_number,
            notes=payment_in.notes,
            created_by=self.current_user_id,
        )
        self.db.add(payment)
        self.db.flush()

        # --- update invoice running totals ---------------------------------
        # Re-derive from the relationship so the new Payment row is included.
        self._recalculate_invoice_totals(invoice)
        invoice.payment_status = self._resolve_payment_status(invoice)

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_payments(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Paginated payment listing.

        ``filters`` may contain ``invoice_id``.
        Returns ``{"items": [...], "total": int}``.
        """
        filters = filters or {}

        query = self.db.query(Payment).filter(Payment.tenant_id == self.tenant_id)

        if "invoice_id" in filters:
            query = query.filter(Payment.invoice_id == filters["invoice_id"])

        if from_date:
            query = query.filter(Payment.payment_date >= datetime.combine(from_date, datetime.min.time()))

        if to_date:
            # include the entire to_date day
            query = query.filter(Payment.payment_date < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))

        total = query.count()

        items = (
            query.order_by(desc(Payment.payment_date))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total}

    # ------------------------------------------------------------------
    # Summary / reporting
    # ------------------------------------------------------------------

    def get_payment_summary(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> PaymentSummary:
        """
        Build the ``PaymentSummary`` shape expected by the ``/summary`` endpoint.

        Composes data from both the invoice-level revenue summary and the
        payment-method breakdown exposed by the repositories.
        """
        # --- date-range revenue from invoices -----------------------------
        revenue = self.invoice_repo.get_revenue_summary(from_date=from_date, to_date=to_date)

        # --- today's collections (payments recorded today) ----------------
        today_payments = self.payment_repo.get_today_payments()
        today_revenue = sum(p.amount for p in today_payments)

        # --- this-month collections ---------------------------------------
        first_of_month = date.today().replace(day=1)
        month_payment_summary = self.payment_repo.get_payment_summary(
            from_date=datetime.combine(first_of_month, datetime.min.time()),
            to_date=datetime.utcnow(),
        )
        this_month_revenue = month_payment_summary.get("total_amount", 0)

        # --- payment-method breakdown (respects the caller's date range) --
        method_breakdown = self.payment_repo.count_by_method(
            from_date=(
                datetime.combine(from_date, datetime.min.time()) if from_date else None
            ),
            to_date=(
                datetime.combine(to_date + timedelta(days=1), datetime.min.time()) if to_date else None
            ),
        )
        # Flatten to {method: total_amount} for the summary schema
        methods_totals: Dict[str, int] = {
            method: info["total"] for method, info in method_breakdown.items()
        }

        return PaymentSummary(
            total_revenue=revenue.get("total_invoiced", 0),
            paid_amount=revenue.get("total_paid", 0),
            pending_amount=revenue.get("total_pending", 0),
            today_revenue=today_revenue,
            this_month_revenue=this_month_revenue,
            payment_methods_breakdown=methods_totals,
        )

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

    def generate_invoice_pdf(self, invoice_id: int) -> Optional[bytes]:
        """
        Generate a PDF representation of the invoice.

        Returns ``None`` when the invoice does not exist so the router can
        respond with 404.  The actual PDF rendering is delegated to a thin
        helper so it can be swapped for a proper templating engine (e.g.
        WeasyPrint / ReportLab) without touching business logic.
        """
        invoice = self.invoice_repo.get_with_items(invoice_id)
        if not invoice:
            return None

        return _render_invoice_pdf(invoice)


# ----------------------------------------------------------------------
# PDF rendering helper  (isolated so it can be replaced independently)
# ----------------------------------------------------------------------


def _render_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Minimal PDF builder using ReportLab.

    If ReportLab is not installed the function falls back to a plain-text
    PDF-like byte stream so the endpoint never crashes in dev.  Replace this
    body with your preferred PDF library (WeasyPrint, fpdf2, etc.).
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from io import BytesIO

        buf = BytesIO()
        c = rl_canvas.Canvas(str(buf), pagesize=A4)
        width, height = A4

        # --- header -------------------------------------------------------
        y = height - 40 * mm
        c.setFont("Helvetica-Bold", 18)
        c.drawString(20 * mm, y, "INVOICE")
        y -= 8 * mm
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, f"Invoice #: {invoice.invoice_number}")
        y -= 5 * mm
        c.drawString(20 * mm, y, f"Date: {invoice.invoice_date}")
        y -= 5 * mm
        if invoice.due_date:
            c.drawString(20 * mm, y, f"Due: {invoice.due_date}")
            y -= 5 * mm
        c.drawString(20 * mm, y, f"Status: {invoice.payment_status.value.title()}")
        y -= 10 * mm

        # --- line items ---------------------------------------------------
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, "Description")
        c.drawString(100 * mm, y, "Qty")
        c.drawString(120 * mm, y, "Unit Price")
        c.drawString(155 * mm, y, "Total")
        y -= 5 * mm
        c.line(20 * mm, y, 185 * mm, y)
        y -= 5 * mm

        c.setFont("Helvetica", 10)
        for item in invoice.invoice_items:
            c.drawString(20 * mm, y, item.description[:50])
            c.drawString(100 * mm, y, str(item.quantity))
            c.drawString(120 * mm, y, _fmt(item.unit_price))
            c.drawString(155 * mm, y, _fmt(item.total_amount))
            y -= 5 * mm

        # --- totals -------------------------------------------------------
        y -= 5 * mm
        c.line(20 * mm, y, 185 * mm, y)
        y -= 5 * mm

        totals = [
            ("Subtotal", invoice.subtotal),
            ("Discount", -invoice.discount_amount),
            ("Tax", invoice.tax_amount),
            ("Total", invoice.total_amount),
            ("Paid", invoice.paid_amount),
            ("Balance Due", invoice.balance_amount),
        ]
        for label, value in totals:
            c.setFont("Helvetica-Bold" if label in ("Total", "Balance Due") else "Helvetica", 10)
            c.drawString(120 * mm, y, label)
            c.drawRightString(185 * mm, y, _fmt(value))
            y -= 5 * mm

        # --- notes --------------------------------------------------------
        if invoice.notes:
            y -= 5 * mm
            c.setFont("Helvetica", 9)
            c.drawString(20 * mm, y, f"Notes: {invoice.notes}")

        c.save()
        return buf.getvalue()

    except ImportError:  # pragma: no cover – fallback when reportlab is absent
        # Return a minimal, valid PDF with plain text so dev environments
        # don't blow up.  Not production-quality; install reportlab.
        return _fallback_text_pdf(invoice)


def _fmt(paise: int) -> str:
    """Format smallest-unit integer as a two-decimal currency string."""
    sign = "-" if paise < 0 else ""
    return f"{sign}{abs(paise) / 100:.2f}"


def _fallback_text_pdf(invoice: Invoice) -> bytes:  # pragma: no cover
    """Bare-bones valid PDF with invoice text when ReportLab is missing."""
    lines = [
        f"Invoice: {invoice.invoice_number}",
        f"Date: {invoice.invoice_date}",
        f"Status: {invoice.payment_status.value}",
        "",
    ]
    for item in invoice.invoice_items:
        lines.append(f"  {item.description}  x{item.quantity}  {_fmt(item.total_amount)}")
    lines.extend([
        "",
        f"Total: {_fmt(invoice.total_amount)}",
        f"Paid:  {_fmt(invoice.paid_amount)}",
        f"Balance: {_fmt(invoice.balance_amount)}",
    ])
    body = "\n".join(lines)

    # Minimal valid PDF 1.0 structure
    stream_content = f"BT /F1 10 Tf 72 750 Td ({body.replace(chr(10), ') Tj 0 -14 Td (')}) Tj ET"
    objects = (
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        "/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        f"4 0 obj<</Length {len(stream_content)}>>\nstream\n{stream_content}\nendstream\nendobj\n"
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    )
    pdf = f"%PDF-1.0\n{objects}xref\n0 6\n\ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
    return pdf.encode("latin-1")