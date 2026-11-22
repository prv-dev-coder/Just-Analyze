"""HTTP routes for Just Analyze.

Thin layer over services.py (writes and per-record reads) and finance.py
(reports). Business errors raised as BusinessError are translated to
fastapi.HTTPException by the ``_translate`` decorator on each route.
"""

import csv
import datetime
import functools
import io
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, constr

try:
    from . import finance
    from . import services as svc
    from .services import BusinessError
except ImportError:  # run with backend/ on sys.path
    import finance
    import services as svc
    from services import BusinessError


router = APIRouter(prefix="/api")

PERIODS = ("today", "month", "all")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _translate(fn):
    """Convert BusinessError raised by the wrapped route into HTTPException."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BusinessError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    return wrapper


def _dump(model):
    """Plain dict from a pydantic model (works on pydantic v1 and v2)."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _check_period(period):
    if period not in PERIODS:
        raise HTTPException(
            status_code=400,
            detail="period must be one of: today, month, all",
        )
    return period


def _today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class ProductIn(BaseModel):
    product_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    gst_percent: Optional[float] = None
    hsn_code: Optional[str] = None
    billing_id: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_rate: Optional[float] = None
    selling_rate: Optional[float] = None
    pre_order_qty: Optional[int] = None
    barcodes: Optional[List[str]] = None


class BarcodeIn(BaseModel):
    barcode: Optional[str] = None


class SupplierIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class PurchaseIn(BaseModel):
    purchase_date: Optional[str] = None
    supplier_id: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None
    amount_paid: Optional[float] = None


class CustomerIn(BaseModel):
    customer_id: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    credit_limit: Optional[float] = None


class InvoiceIn(BaseModel):
    customer_id: Optional[str] = None
    payment_type: Optional[str] = None
    invoice_date: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None


class PaymentIn(BaseModel):
    customer_id: Optional[str] = None
    invoice_no: Optional[str] = None
    amount: Optional[float] = None
    payment_date: Optional[str] = None
    note: Optional[str] = None


class ExpenseIn(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    kind: Optional[str] = None
    status: Optional[str] = None
    expense_date: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class OpeningBalanceIn(BaseModel):
    value: float


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@router.get("/products")
@_translate
def list_products():
    return svc.list_products()


@router.post("/products")
@_translate
def create_product(body: ProductIn):
    return svc.create_product(_dump(body))


@router.get("/products/lookup")
@_translate
def lookup_product(q: str = Query("")):
    return svc.lookup_product(q)


@router.get("/products/{product_id}")
@_translate
def get_product(product_id: str):
    return svc.get_product(product_id)


@router.post("/products/{product_id}/barcodes")
@_translate
def add_barcode(product_id: str, body: BarcodeIn):
    return svc.add_barcode(product_id, body.barcode)


# ---------------------------------------------------------------------------
# Suppliers and purchases
# ---------------------------------------------------------------------------

@router.get("/suppliers")
@_translate
def list_suppliers():
    return svc.list_suppliers()


@router.post("/suppliers")
@_translate
def create_supplier(body: SupplierIn):
    return svc.create_supplier(_dump(body))


@router.get("/purchases")
@_translate
def list_purchases():
    return svc.list_purchases()


@router.post("/purchases")
@_translate
def create_purchase(body: PurchaseIn):
    return svc.create_purchase(_dump(body))


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@router.get("/customers")
@_translate
def list_customers():
    return svc.list_customers()


@router.post("/customers")
@_translate
def create_customer(body: CustomerIn):
    return svc.create_customer(_dump(body))


@router.get("/customers/search")
@_translate
def search_customers(q: str = Query("")):
    return svc.search_customers(q)


@router.get("/customers/{customer_id}")
@_translate
def get_customer(customer_id: str):
    return svc.get_customer(customer_id)


# ---------------------------------------------------------------------------
# Invoices and payments
# ---------------------------------------------------------------------------

@router.get("/invoices")
@_translate
def list_invoices():
    return svc.list_invoices()


@router.post("/invoices")
@_translate
def create_invoice(body: InvoiceIn):
    return svc.create_invoice(_dump(body))


@router.get("/invoices/{invoice_no}")
@_translate
def get_invoice(invoice_no: str):
    return svc.get_invoice(invoice_no)


@router.get("/payments")
@_translate
def list_payments():
    return svc.list_payments()


@router.post("/payments")
@_translate
def record_payment(body: PaymentIn):
    return svc.record_payment(_dump(body))


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@router.get("/expenses")
@_translate
def list_expenses():
    return svc.list_expenses()


@router.post("/expenses")
@_translate
def create_expense(body: ExpenseIn):
    return svc.create_expense(_dump(body))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.get("/dashboard")
@_translate
def dashboard(period: str = Query("month")):
    _check_period(period)
    return finance.dashboard(period, _today())


@router.get("/cashflow")
@_translate
def cashflow(period: str = Query("month")):
    _check_period(period)
    return finance.cashflow_breakdown(period, _today())


@router.get("/receivables")
@_translate
def receivables():
    return finance.receivables_report(_today())


_PAYMENTS_CSV_HEADER = [
    "Customer Name",
    "Customer ID",
    "Invoice No",
    "Invoice Date",
    "Invoice Amount",
    "Amount Paid",
    "Outstanding",
    "Status",
    "Payment Dates",
]


@router.get("/reports/payments.csv")
@_translate
def payments_csv():
    report = finance.payments_report_rows()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_PAYMENTS_CSV_HEADER)
    for r in report["rows"]:
        writer.writerow([
            r["customer_name"],
            r["customer_id"],
            r["invoice_no"],
            r["invoice_date"],
            r["total_amount"],
            r["amount_paid"],
            r["outstanding"],
            r["status"],
            r["payment_dates"],
        ])
    writer.writerow([
        "TOTAL",
        "",
        "",
        "",
        report["total_amount"],
        report["amount_paid"],
        report["outstanding"],
        "",
        "",
    ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payments-report.csv"'},
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings")
@_translate
def get_settings():
    return svc.get_settings()


@router.put("/settings/opening-balance")
@_translate
def set_opening_balance(body: OpeningBalanceIn):
    return svc.set_opening_balance(body.value)


# ---------------------------------------------------------------------------
# AI agent
# ---------------------------------------------------------------------------

DEFAULT_AGENT_LLM_URL = "http://localhost:11434"
DEFAULT_AGENT_LLM_MODEL = "llama3.2"


class AgentMessage(BaseModel):
    text: constr(min_length=1)


def _agent_flow():
    """Load the agent flow module lazily, using the same import pattern as above."""
    try:
        from .agent import flow
    except ImportError:  # run with backend/ on sys.path
        from agent import flow
    return flow


@router.post("/agent/message")
@_translate
def agent_message(body: AgentMessage):
    flow = _agent_flow()
    return flow.handle_message(body.text, _today())


@router.post("/agent/actions/{action_id}/confirm")
@_translate
def agent_confirm(action_id: str):
    flow = _agent_flow()
    return flow.confirm_action(action_id, _today())


@router.post("/agent/actions/{action_id}/cancel")
@_translate
def agent_cancel(action_id: str):
    flow = _agent_flow()
    return flow.cancel_action(action_id)


@router.get("/agent/actions")
@_translate
def agent_actions():
    flow = _agent_flow()
    return {"pending": flow.list_pending_actions()}


@router.get("/agent/status")
@_translate
def agent_status():
    return {
        "model": os.environ.get("AGENT_LLM_MODEL") or DEFAULT_AGENT_LLM_MODEL,
        "url": os.environ.get("AGENT_LLM_URL") or DEFAULT_AGENT_LLM_URL,
    }
