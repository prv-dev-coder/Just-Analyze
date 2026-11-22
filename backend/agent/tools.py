"""Allowlisted agent tools: argument models, validation, description and execution.

Only the intents listed in _MODELS can be validated or executed. Anything else
raises UnknownIntent. Write intents must be confirmed by the flow layer before
execute() is called; this module does not confirm anything itself.
"""

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

try:
    from ..services import (create_product, lookup_product, create_customer, search_customers, get_customer, create_invoice, record_payment, create_expense, create_purchase, BusinessError)
    from ..finance import dashboard, receivables_report
except ImportError:
    from services import (create_product, lookup_product, create_customer, search_customers, get_customer, create_invoice, record_payment, create_expense, create_purchase, BusinessError)
    from finance import dashboard, receivables_report


class UnknownIntent(Exception):
    """Raised when an intent is not in the allowlist."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CreateProductArgs(_Base):
    product_id: str
    name: str
    purchase_rate: float
    selling_rate: float
    gst_percent: float = 0
    category: Optional[str] = None
    hsn_code: Optional[str] = None
    barcodes: list[str] = Field(default_factory=list)


class FindProductArgs(_Base):
    query: str


class RecordPurchaseArgs(_Base):
    product_id: str
    qty: int
    rate: float
    purchase_date: Optional[str] = None
    supplier_id: Optional[int] = None
    amount_paid: float = 0


class CreateExpenseArgs(_Base):
    name: str
    amount: float
    category: Optional[str] = None
    kind: str = "other"
    status: str = "pending"
    expense_date: Optional[str] = None
    description: Optional[str] = None


class CreateCustomerArgs(_Base):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    credit_limit: float = 0


class FindCustomerArgs(_Base):
    query: str


class RecordPaymentArgs(_Base):
    customer_id: str
    invoice_no: str
    amount: float
    payment_date: Optional[str] = None


class CreateInvoiceArgs(_Base):
    customer_id: str
    payment_type: str
    items: list[dict]

    @field_validator("items")
    @classmethod
    def _check_items(cls, items: list[dict]) -> list[dict]:
        # Emptiness is reported as a missing field by validate(), not here.
        checked = []
        for idx, item in enumerate(items):
            product_id = item.get("product_id")
            if product_id is None or (isinstance(product_id, str) and product_id.strip() == ""):
                raise ValueError(f"items[{idx}] needs a product_id")
            qty = item.get("qty")
            if isinstance(qty, str) and qty.strip().isdigit():
                qty = int(qty.strip())
            if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
                raise ValueError(f"items[{idx}].qty must be a whole number greater than 0")
            new_item = dict(item)
            new_item["qty"] = qty
            checked.append(new_item)
        return checked


class CustomerOutstandingArgs(_Base):
    customer_id: str


class FinancialSummaryArgs(_Base):
    period: str = "month"


_MODELS: dict[str, type[BaseModel]] = {
    "create_product": CreateProductArgs,
    "find_product": FindProductArgs,
    "record_purchase": RecordPurchaseArgs,
    "create_expense": CreateExpenseArgs,
    "create_customer": CreateCustomerArgs,
    "find_customer": FindCustomerArgs,
    "record_payment": RecordPaymentArgs,
    "create_invoice": CreateInvoiceArgs,
    "customer_outstanding": CustomerOutstandingArgs,
    "financial_summary": FinancialSummaryArgs,
}

# Fields without defaults on each model. Empty values count as missing.
MANDATORY: dict[str, tuple[str, ...]] = {
    "create_product": ("product_id", "name", "purchase_rate", "selling_rate"),
    "find_product": ("query",),
    "record_purchase": ("product_id", "qty", "rate"),
    "create_expense": ("name", "amount"),
    "create_customer": ("name",),
    "find_customer": ("query",),
    "record_payment": ("customer_id", "invoice_no", "amount"),
    "create_invoice": ("customer_id", "payment_type", "items"),
    "customer_outstanding": ("customer_id",),
    "financial_summary": (),
}

WRITE_INTENTS = {"create_product", "record_purchase", "create_expense", "create_customer", "record_payment", "create_invoice"}
READ_INTENTS = {"find_product", "find_customer", "customer_outstanding", "financial_summary"}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _format_error(err: dict) -> str:
    field = ".".join(str(part) for part in err.get("loc", ())) or "arguments"
    return f"Invalid value for '{field}': {err.get('msg', 'not valid')}"


def validate(intent: str, args: dict) -> tuple[dict, list[str]]:
    """Return (clean_args, missing_fields) for an intent.

    Raises UnknownIntent for intents outside the allowlist and ValueError when a
    present field fails validation.
    """
    model_cls = _MODELS.get(intent)
    if model_cls is None:
        raise UnknownIntent(f"Unknown intent: {intent}")

    raw = args or {}
    fields = model_cls.model_fields
    # Empty values are dropped so that absent and empty both show up as missing.
    data = {k: v for k, v in raw.items() if k in fields and not _is_empty(v)}
    missing = [name for name in MANDATORY.get(intent, ()) if name not in data]

    try:
        model = model_cls.model_validate(data)
    except ValidationError as exc:
        errors = exc.errors()
        real = [e for e in errors if e.get("type") != "missing"]
        if real:
            raise ValueError(_format_error(real[0])) from None
        # Only missing fields failed; no value is invented. The present values are
        # returned as given and fully validated once the caller supplies the rest.
        return dict(data), missing

    return model.model_dump(exclude_none=True), missing


def _money(value: Any) -> str:
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}"


def describe(intent: str, clean: dict) -> str:
    """One human line describing the action with its actual values."""
    if intent == "create_product":
        return (f"Create product {clean.get('product_id')} ({clean.get('name')}) "
                f"with selling price {_money(clean.get('selling_rate', 0))}")
    if intent == "record_purchase":
        qty = clean.get("qty", 0)
        rate = clean.get("rate", 0)
        total = _money(float(qty) * float(rate))
        return (f"Record purchase of {qty} x {clean.get('product_id')} at "
                f"{_money(rate)} each (total {total})")
    if intent == "create_expense":
        return (f"Record expense {clean.get('name')} of {_money(clean.get('amount', 0))} "
                f"({clean.get('status', 'pending')})")
    if intent == "create_customer":
        return (f"Create customer {clean.get('name')} "
                f"(credit limit {_money(clean.get('credit_limit', 0))})")
    if intent == "record_payment":
        return (f"Record payment of {_money(clean.get('amount', 0))} from "
                f"{clean.get('customer_id')} against {clean.get('invoice_no')}")
    if intent == "create_invoice":
        count = len(clean.get("items") or [])
        return (f"Create {clean.get('payment_type')} invoice for "
                f"{clean.get('customer_id')} with {count} item(s)")
    if intent == "find_product":
        return f"Look up product {clean.get('query')}"
    if intent == "find_customer":
        return f"Search customers for {clean.get('query')}"
    if intent == "customer_outstanding":
        return f"Show outstanding balance for {clean.get('customer_id')}"
    if intent == "financial_summary":
        return f"Show {clean.get('period', 'month')} financial summary"
    raise UnknownIntent(f"Unknown intent: {intent}")


def _drop_none(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}


def execute(intent: str, clean: dict) -> dict:
    """Run the matching service call. BusinessError propagates to the caller."""
    if intent == "create_product":
        return create_product(clean)
    if intent == "find_product":
        return {"product": lookup_product(clean.get("query"))}
    if intent == "record_purchase":
        payload = _drop_none({
            "purchase_date": clean.get("purchase_date"),
            "supplier_id": clean.get("supplier_id"),
            "amount_paid": clean.get("amount_paid"),
            "items": [{
                "product_id": clean.get("product_id"),
                "qty": clean.get("qty"),
                "rate": clean.get("rate"),
            }],
        })
        return create_purchase(payload)
    if intent == "create_expense":
        return create_expense(clean)
    if intent == "create_customer":
        return create_customer(clean)
    if intent == "find_customer":
        return {"customers": search_customers(clean.get("query"))}
    if intent == "record_payment":
        payload = _drop_none({
            "customer_id": clean.get("customer_id"),
            "invoice_no": clean.get("invoice_no"),
            "amount": clean.get("amount"),
            "payment_date": clean.get("payment_date"),
        })
        return record_payment(payload)
    if intent == "create_invoice":
        return create_invoice({
            "customer_id": clean.get("customer_id"),
            "payment_type": clean.get("payment_type"),
            "items": clean.get("items"),
        })
    if intent == "customer_outstanding":
        customer = get_customer(clean.get("customer_id"))
        return {
            "customer_id": customer.get("customer_id"),
            "name": customer.get("name"),
            "total_outstanding": customer.get("total_outstanding"),
            "available_credit": customer.get("available_credit"),
        }
    if intent == "financial_summary":
        today = datetime.date.today().isoformat()
        summary = dashboard(clean.get("period", "month"), today)
        return {
            "sales_total": summary.get("sales_total"),
            "available_cash": summary.get("available_cash"),
            "receivables": summary.get("receivables"),
            "payables": summary.get("payables"),
            "health": summary.get("health"),
        }
    raise UnknownIntent(f"Unknown intent: {intent}")
