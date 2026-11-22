"""End-to-end workflow tests for Just Analyze, run through the FastAPI TestClient.

Each test gets its own temporary SQLite database: an autouse fixture points
backend.db.DB_PATH at a file inside pytest's tmp_path and creates the schema.
"""

import csv
import io
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from backend import db as db_module  # noqa: E402
from backend.main import app  # noqa: E402


CSV_HEADER = [
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


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = str(tmp_path / "test_justanalyze.db")
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    yield path


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_product(client, product_id="P001", barcodes=None, purchase_rate=60.0,
                    selling_rate=100.0, gst_percent=0.0):
    body = {
        "product_id": product_id,
        "name": f"Product {product_id}",
        "purchase_rate": purchase_rate,
        "selling_rate": selling_rate,
        "gst_percent": gst_percent,
    }
    if barcodes is not None:
        body["barcodes"] = barcodes
    r = client.post("/api/products", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _create_supplier(client, name="Sharma Traders"):
    r = client.post("/api/suppliers", json={"name": name, "phone": "9000000000"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _purchase(client, supplier_id, product_id, qty, rate, amount_paid):
    r = client.post("/api/purchases", json={
        "supplier_id": supplier_id,
        "items": [{"product_id": product_id, "qty": qty, "rate": rate}],
        "amount_paid": amount_paid,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _create_customer(client, name="Ravi Kumar", credit_limit=1000.0):
    r = client.post("/api/customers", json={"name": name, "credit_limit": credit_limit})
    assert r.status_code == 200, r.text
    return r.json()["customer_id"]


def _invoice(client, customer_id, payment_type, items):
    return client.post("/api/invoices", json={
        "customer_id": customer_id,
        "payment_type": payment_type,
        "items": items,
    })


def _stock(client, product_id):
    return client.get(f"/api/products/{product_id}").json()["stock_qty"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_product_with_barcode_lookup_and_duplicate(client):
    created = _create_product(client, "P001", barcodes=["8900000000011"])
    assert created["product_id"] == "P001"
    assert "8900000000011" in created["barcodes"]

    by_barcode = client.get("/api/products/lookup", params={"q": "8900000000011"})
    by_id = client.get("/api/products/P001")
    assert by_barcode.status_code == 200
    assert by_id.status_code == 200
    assert by_barcode.json()["product_id"] == by_id.json()["product_id"] == "P001"
    assert by_barcode.json()["id"] == by_id.json()["id"]

    dup = client.post("/api/products", json={
        "product_id": "P001", "name": "Duplicate", "selling_rate": 10, "purchase_rate": 5,
    })
    assert dup.status_code == 409


def test_purchase_increases_stock_and_records_pending(client):
    _create_product(client, "P001")
    supplier_id = _create_supplier(client)

    result = _purchase(client, supplier_id, "P001", qty=10, rate=60.0, amount_paid=200.0)

    assert result["total"] == 600.0
    assert result["amount_paid"] == 200.0
    assert result["pending"] == 400.0
    assert _stock(client, "P001") == 10


def test_cash_invoice_reduces_stock_and_records_payment(client):
    _create_product(client, "P001")
    _purchase(client, _create_supplier(client), "P001", qty=10, rate=60.0, amount_paid=600.0)
    customer_id = _create_customer(client)

    r = _invoice(client, customer_id, "cash", [{"product_id": "P001", "qty": 3}])

    assert r.status_code == 200, r.text
    invoice = r.json()
    assert invoice["status"] == "paid"
    assert _stock(client, "P001") == 7

    payments = client.get("/api/payments").json()
    assert any(p["invoice_no"] == invoice["invoice_no"] for p in payments)


def test_credit_invoice_within_limit_succeeds(client):
    _create_product(client, "P001", selling_rate=100.0)
    _purchase(client, _create_supplier(client), "P001", qty=20, rate=60.0, amount_paid=1200.0)
    customer_id = _create_customer(client, credit_limit=1000.0)

    r = _invoice(client, customer_id, "credit", [{"product_id": "P001", "qty": 5}])

    assert r.status_code == 200, r.text
    invoice = r.json()
    assert invoice["status"] == "unpaid"
    assert invoice["outstanding"] == 500.0


def test_credit_invoice_over_available_credit_returns_409(client):
    _create_product(client, "P001", selling_rate=100.0)
    _purchase(client, _create_supplier(client), "P001", qty=20, rate=60.0, amount_paid=1200.0)
    customer_id = _create_customer(client, credit_limit=1000.0)

    first = _invoice(client, customer_id, "credit", [{"product_id": "P001", "qty": 5}])
    assert first.status_code == 200, first.text

    # 500 already outstanding; another 600 would exceed the 1000 limit.
    second = _invoice(client, customer_id, "credit", [{"product_id": "P001", "qty": 6}])
    assert second.status_code == 409


def test_insufficient_stock_returns_409_and_leaves_stock_unchanged(client):
    _create_product(client, "P001")
    _purchase(client, _create_supplier(client), "P001", qty=2, rate=60.0, amount_paid=120.0)
    customer_id = _create_customer(client)

    r = _invoice(client, customer_id, "cash", [{"product_id": "P001", "qty": 5}])

    assert r.status_code == 409
    assert _stock(client, "P001") == 2
    assert client.get("/api/invoices").json() == []


def test_partial_payment_and_overpayment(client):
    _create_product(client, "P001", selling_rate=100.0)
    _purchase(client, _create_supplier(client), "P001", qty=20, rate=60.0, amount_paid=1200.0)
    customer_id = _create_customer(client, credit_limit=1000.0)
    invoice = _invoice(
        client, customer_id, "credit", [{"product_id": "P001", "qty": 5}]
    ).json()
    invoice_no = invoice["invoice_no"]

    paid = client.post("/api/payments", json={
        "customer_id": customer_id, "invoice_no": invoice_no, "amount": 200.0,
    })
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "partially_paid"
    assert paid.json()["outstanding"] == 300.0

    current = client.get(f"/api/invoices/{invoice_no}").json()
    assert current["outstanding"] == 300.0

    over = client.post("/api/payments", json={
        "customer_id": customer_id, "invoice_no": invoice_no, "amount": 400.0,
    })
    assert over.status_code == 409
    assert client.get(f"/api/invoices/{invoice_no}").json()["outstanding"] == 300.0


def test_customer_search_finds_new_customer(client):
    _create_customer(client, name="Anita Rao")
    found = client.get("/api/customers/search", params={"q": "Anita"})
    assert found.status_code == 200
    assert [c["name"] for c in found.json()] == ["Anita Rao"]

    assert client.get("/api/customers/search", params={"q": "Bharat"}).json() == []

    _create_customer(client, name="Bharat Motors")
    found_new = client.get("/api/customers/search", params={"q": "Bharat"})
    assert [c["name"] for c in found_new.json()] == ["Bharat Motors"]


def test_pending_expense_does_not_reduce_cash_but_paid_expense_does(client):
    r = client.put("/api/settings/opening-balance", json={"value": 1000.0})
    assert r.status_code == 200, r.text

    def available_cash():
        return client.get("/api/dashboard", params={"period": "month"}).json()["available_cash"]

    assert available_cash() == 1000.0

    pending = client.post("/api/expenses", json={
        "name": "Electricity", "amount": 400.0, "kind": "fixed", "status": "pending",
    })
    assert pending.status_code == 200, pending.text
    assert available_cash() == 1000.0

    paid = client.post("/api/expenses", json={
        "name": "Shop rent", "amount": 300.0, "kind": "fixed", "status": "paid",
    })
    assert paid.status_code == 200, paid.text
    assert available_cash() == 700.0


def test_dashboard_month_returns_health_with_reasons(client):
    r = client.get("/api/dashboard", params={"period": "month"})

    assert r.status_code == 200, r.text
    health = r.json()["health"]
    assert health["status"] in ("GREEN", "YELLOW", "RED")
    assert isinstance(health["reasons"], list)
    assert len(health["reasons"]) > 0


def test_payments_csv_export_has_header_row(client):
    r = client.get("/api/reports/payments.csv")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    header = next(csv.reader(io.StringIO(r.text)))
    assert header == CSV_HEADER
