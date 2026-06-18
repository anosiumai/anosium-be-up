"""
Invoice PDF rendering via ReportLab.

Single public function: render_invoice_pdf(invoice) -> bytes
Called by BillingService.generate_invoice_pdf().

Run the self-test:
    python -m core.pdf_renderer
"""

from io import BytesIO
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

if TYPE_CHECKING:
    from models.billing import Invoice


def render_invoice_pdf(invoice: "Invoice") -> bytes:
    """Return a PDF byte string for *invoice*."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    LEFT = 20 * mm

    y = H - 30 * mm

    # ── header ────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 16)
    c.drawString(LEFT, y, "INVOICE")
    y -= 7 * mm

    c.setFont("Helvetica", 10)
    for label, value in [
        ("Invoice #:", invoice.invoice_number),
        ("Date:", str(invoice.invoice_date)),
        ("Due:", str(invoice.due_date or "—")),
        ("Status:", invoice.payment_status.value.title()),
    ]:
        c.drawString(LEFT, y, f"{label} {value}")
        y -= 5 * mm

    y -= 5 * mm

    # ── line items header ─────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10)
    for x, txt in [(LEFT, "Description"), (120*mm, "Qty"), (140*mm, "Unit"), (165*mm, "Total")]:
        c.drawString(x, y, txt)
    y -= 4 * mm
    c.line(LEFT, y, 190*mm, y)
    y -= 5 * mm

    # ── line items ────────────────────────────────────────────────────
    c.setFont("Helvetica", 9)
    for item in invoice.invoice_items:
        c.drawString(LEFT, y, item.description[:55])
        c.drawString(120*mm, y, str(item.quantity))
        c.drawRightString(155*mm, y, _fmt(item.unit_price))
        c.drawRightString(185*mm, y, _fmt(item.total_amount))
        y -= 5 * mm

    y -= 3 * mm
    c.line(LEFT, y, 190*mm, y)
    y -= 5 * mm

    # ── totals ────────────────────────────────────────────────────────
    for label, amount, bold in [
        ("Subtotal",    invoice.subtotal,         False),
        ("Discount",   -invoice.discount_amount,  False),
        ("Tax",         invoice.tax_amount,        False),
        ("Total",       invoice.total_amount,      True),
        ("Paid",        invoice.paid_amount,        False),
        ("Balance Due", invoice.balance_amount,    True),
    ]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(130*mm, y, label)
        c.drawRightString(185*mm, y, _fmt(amount))
        y -= 5 * mm

    if invoice.notes:
        y -= 5 * mm
        c.setFont("Helvetica", 9)
        c.drawString(LEFT, y, f"Notes: {invoice.notes}")

    c.save()
    return buf.getvalue()


def _fmt(paise: int) -> str:
    """Smallest-unit integer → two-decimal currency string."""
    sign = "-" if paise < 0 else ""
    return f"{sign}{abs(paise) / 100:.2f}"


# ── self-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from types import SimpleNamespace
    from datetime import date

    # ponytail: SimpleNamespace fakes the ORM object cheaply; no DB needed
    item = SimpleNamespace(
        description="General Consultation",
        quantity=1,
        unit_price=50000,   # ₹500.00
        tax_amount=4500,
        total_amount=54500,
    )
    inv = SimpleNamespace(
        invoice_number="INV-20260617-0001",
        invoice_date=date.today(),
        due_date=date.today(),
        payment_status=SimpleNamespace(value="pending"),
        invoice_items=[item],
        subtotal=50000,
        discount_amount=0,
        tax_amount=4500,
        total_amount=54500,
        paid_amount=0,
        balance_amount=54500,
        notes="Thank you for choosing our clinic.",
    )

    pdf = render_invoice_pdf(inv)
    assert pdf[:4] == b"%PDF", "output is not a valid PDF"
    assert len(pdf) > 1000, "PDF suspiciously small"
    print(f"OK — {len(pdf)} bytes, starts with {pdf[:8]!r}")