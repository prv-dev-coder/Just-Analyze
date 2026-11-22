"""Insert sample data for Just Analyze through the services layer.

Run from the project root:  python scripts/seed_demo.py

Idempotent: if product P001 already exists, a message is printed and the
script exits with status 0 without inserting anything.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import services as svc  # noqa: E402
from backend.db import init_db  # noqa: E402


def _seed_products():
    """Three products, each with one or two barcodes."""
    products = [
        {
            "product_id": "P001",
            "name": "Basmati Rice 5kg",
            "category": "Grocery",
            "hsn_code": "1006",
            "purchase_rate": 300.0,
            "selling_rate": 350.0,
            "gst_percent": 5,
            "barcodes": ["8900000000011", "8900000000012"],
        },
        {
            "product_id": "P002",
            "name": "Sugar 1kg",
            "category": "Grocery",
            "hsn_code": "1701",
            "purchase_rate": 40.0,
            "selling_rate": 48.0,
            "gst_percent": 5,
            "barcodes": ["8900000000028"],
        },
        {
            "product_id": "P003",
            "name": "A4 Notebook 200 pages",
            "category": "Stationery",
            "hsn_code": "4820",
            "purchase_rate": 25.0,
            "selling_rate": 35.0,
            "gst_percent": 12,
            "barcodes": ["8900000000035", "8900000000036"],
        },
    ]
    for data in products:
        svc.create_product(data)
    return [p["product_id"] for p in products], {p["product_id"]: p["purchase_rate"] for p in products}


def main():
    init_db()

    existing = {p["product_id"] for p in svc.list_products()}
    if "P001" in existing:
        print("Demo data already present (product P001 exists). Nothing inserted.")
        return 0

    product_ids, purchase_rates = _seed_products()

    suppliers = [
        svc.create_supplier({"name": "Sharma Traders", "phone": "9876500001", "address": "Main Road"}),
        svc.create_supplier({"name": "Metro Wholesale", "phone": "9876500002", "address": "Market Yard"}),
    ]

    # One purchase per product, each paid partially so pending balances exist.
    for index, product_id in enumerate(product_ids):
        supplier = suppliers[index % len(suppliers)]
        qty = 20
        rate = purchase_rates[product_id]
        total = qty * rate
        svc.create_purchase({
            "supplier_id": supplier["id"],
            "items": [{"product_id": product_id, "qty": qty, "rate": rate}],
            "amount_paid": round(total / 2, 2),
        })

    customers = [
        svc.create_customer({
            "name": "Ravi Kumar",
            "phone": "9123400001",
            "address": "12 Lake View",
            "credit_limit": 5000,
        }),
        svc.create_customer({
            "name": "Anita Rao",
            "phone": "9123400002",
            "address": "7 Station Road",
            "credit_limit": 3000,
        }),
    ]
    cash_customer, credit_customer = customers

    # Cash invoice.
    svc.create_invoice({
        "customer_id": cash_customer["customer_id"],
        "payment_type": "cash",
        "items": [
            {"product_id": "P001", "qty": 2},
            {"product_id": "P002", "qty": 3},
        ],
    })

    # Credit invoice, followed by a partial payment against it.
    credit_invoice = svc.create_invoice({
        "customer_id": credit_customer["customer_id"],
        "payment_type": "credit",
        "items": [
            {"product_id": "P003", "qty": 4},
            {"product_id": "P001", "qty": 1},
        ],
    })
    svc.record_payment({
        "customer_id": credit_customer["customer_id"],
        "invoice_no": credit_invoice["invoice_no"],
        "amount": 200.0,
        "note": "part payment",
    })

    svc.create_expense({
        "name": "Shop rent",
        "amount": 1500.0,
        "kind": "fixed",
        "status": "paid",
        "category": "Rent",
    })

    print("Demo data inserted: 3 products, 2 suppliers, 3 purchases, "
          "2 customers, 2 invoices, 1 payment, 1 expense.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
