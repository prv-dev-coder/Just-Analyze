"""Write-side business logic for Just Analyze.

Costing method
--------------
Each invoice line records ``cost_rate`` = ``products.purchase_rate`` at the moment
of sale. ``products.purchase_rate`` is updated by every purchase line (the rate of
the latest purchase line wins), so the cost captured on an invoice line is the
purchase rate that was current when that line was sold. Profit later is
``(unit_price - cost_rate) * qty`` on each line.

Tax convention
--------------
``selling_rate`` is GST-EXCLUSIVE. GST is added on top at billing:
``line_taxable = qty * selling_rate``, ``line_gst = line_taxable * gst_percent / 100``,
``line_total = line_taxable + line_gst``. All money values are rounded to 2 decimals.

This module only WRITES (and reads back what it just wrote for its own return
values). Financial reporting lives in finance.py.

Errors are raised as ``BusinessError(status_code, detail)``:
400 invalid input, 404 not found, 409 conflict (duplicate, insufficient stock,
credit limit exceeded, overpayment).
"""

import math
import sqlite3
from datetime import date, datetime

try:
    from .db import get_conn
except ImportError:  # run with backend/ on sys.path
    from db import get_conn


class BusinessError(Exception):
    """A rule violation that maps directly to an HTTP-style status code."""

    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _bad(msg):
    return BusinessError(400, msg)


def _not_found(msg):
    return BusinessError(404, msg)


def _conflict(msg):
    return BusinessError(409, msg)


def _today():
    return date.today().isoformat()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _require_dict(data):
    if not isinstance(data, dict):
        raise _bad("request body must be an object")


def _to_number(value, field):
    if value is None or isinstance(value, bool):
        raise _bad(f"{field} must be a number")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise _bad(f"{field} must be a number")
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _bad(f"{field} must be a number")
    return float(value)


def _to_int(value, field):
    if value is None or isinstance(value, bool):
        raise _bad(f"{field} must be an integer")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            raise _bad(f"{field} must be an integer")
    if not isinstance(value, int):
        raise _bad(f"{field} must be an integer")
    return value


def _req_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _bad(f"{key} is required")
    return value.strip()


def _opt_text(data, key):
    value = data.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_or_today(data, key):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return _today()
    return _check_date(value, key)


def _check_date(value, key):
    if not isinstance(value, str):
        raise _bad(f"{key} must be a date in yyyy-mm-dd format")
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        raise _bad(f"{key} must be a date in yyyy-mm-dd format")
    return value.strip()


def _money_field(data, key, default=0.0):
    """Optional non-negative money value, rounded to 2 decimals."""
    value = data.get(key)
    if value is None:
        return round(float(default), 2)
    number = _to_number(value, key)
    if number < 0:
        raise _bad(f"{key} must be >= 0")
    return round(number, 2)


def _money_required(data, key):
    if data.get(key) is None:
        raise _bad(f"{key} is required")
    return _money_field(data, key)


def _items_list(data):
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise _bad("items must be a non-empty list")
    return items


def _tx(work):
    """Run work(conn) inside one BEGIN IMMEDIATE ... COMMIT/ROLLBACK block."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = work(conn)
        except sqlite3.IntegrityError as exc:
            _rollback(conn)
            raise _conflict(f"conflict: {exc}") from exc
        except BaseException:
            _rollback(conn)
            raise
        conn.execute("COMMIT")
        return result
    finally:
        conn.close()


def _read(work):
    """Run work(conn) for reads (no explicit transaction)."""
    conn = get_conn()
    try:
        return work(conn)
    finally:
        conn.close()


def _rollback(conn):
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


# ---------------------------------------------------------------------------
# Products and barcodes
# ---------------------------------------------------------------------------

def _product_row_to_dict(conn, row):
    data = dict(row)
    data["barcodes"] = [
        r["barcode"]
        for r in conn.execute(
            "SELECT barcode FROM product_barcodes WHERE product_pk = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
    ]
    data["profit_margin"] = round(row["selling_rate"] - row["purchase_rate"], 2)
    return data


def _product_by_product_id(conn, product_id):
    row = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    if row is None:
        raise _not_found(f"product not found: {product_id}")
    return row


def _resolve_product(conn, item):
    """Resolve an item dict {product_id | barcode} to a products row (404 if none)."""
    _require_dict(item)
    product_id = item.get("product_id")
    barcode = item.get("barcode")
    if product_id is not None and str(product_id).strip():
        key = str(product_id).strip()
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (key,)
        ).fetchone()
    elif barcode is not None and str(barcode).strip():
        key = str(barcode).strip()
        row = conn.execute(
            "SELECT p.* FROM products p "
            "JOIN product_barcodes b ON b.product_pk = p.id "
            "WHERE b.barcode = ?",
            (key,),
        ).fetchone()
    else:
        raise _bad("each item needs a product_id or a barcode")
    if row is None:
        raise _not_found(f"product not found: {key}")
    return row


def _ensure_barcodes_free(conn, barcodes):
    for code in barcodes:
        if conn.execute(
            "SELECT 1 FROM product_barcodes WHERE barcode = ?", (code,)
        ).fetchone():
            raise _conflict(f"barcode already exists: {code}")


def create_product(data):
    _require_dict(data)
    product_id = _req_text(data, "product_id")
    name = _req_text(data, "name")
    purchase_rate = _money_field(data, "purchase_rate", 0)
    selling_rate = _money_field(data, "selling_rate", 0)

    gst_raw = data.get("gst_percent")
    gst_percent = 0.0 if gst_raw is None else _to_number(gst_raw, "gst_percent")
    if not 0 <= gst_percent <= 100:
        raise _bad("gst_percent must be between 0 and 100")

    pre_order_raw = data.get("pre_order_qty")
    pre_order_qty = 0 if pre_order_raw is None else _to_int(pre_order_raw, "pre_order_qty")
    if pre_order_qty < 0:
        raise _bad("pre_order_qty must be >= 0")

    barcodes_raw = data.get("barcodes") or []
    if not isinstance(barcodes_raw, list):
        raise _bad("barcodes must be a list of strings")
    barcodes = []
    for code in barcodes_raw:
        if not isinstance(code, str) or not code.strip():
            raise _bad("barcodes must be a list of non-empty strings")
        code = code.strip()
        if code not in barcodes:
            barcodes.append(code)

    category = _opt_text(data, "category")
    hsn_code = _opt_text(data, "hsn_code")
    billing_id = _opt_text(data, "billing_id")
    purchase_date = data.get("purchase_date")
    if purchase_date is not None and str(purchase_date).strip():
        purchase_date = _check_date(purchase_date, "purchase_date")
    else:
        purchase_date = None

    def work(conn):
        if conn.execute(
            "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
        ).fetchone():
            raise _conflict(f"product_id already exists: {product_id}")
        _ensure_barcodes_free(conn, barcodes)
        cur = conn.execute(
            "INSERT INTO products (product_id, name, category, gst_percent, hsn_code, "
            "billing_id, purchase_date, selling_rate, purchase_rate, pre_order_qty, stock_qty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (
                product_id, name, category, gst_percent, hsn_code, billing_id,
                purchase_date, selling_rate, purchase_rate, pre_order_qty,
            ),
        )
        pk = cur.lastrowid
        for code in barcodes:
            conn.execute(
                "INSERT INTO product_barcodes (barcode, product_pk) VALUES (?, ?)",
                (code, pk),
            )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (pk,)).fetchone()
        return _product_row_to_dict(conn, row)

    return _tx(work)


def get_product(product_id):
    def work(conn):
        row = _product_by_product_id(conn, str(product_id).strip())
        return _product_row_to_dict(conn, row)

    return _read(work)


def list_products():
    def work(conn):
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [_product_row_to_dict(conn, r) for r in rows]

    return _read(work)


def lookup_product(q):
    key = str(q or "").strip()
    if not key:
        raise _bad("query is required")

    def work(conn):
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ? "
            "OR id IN (SELECT product_pk FROM product_barcodes WHERE barcode = ?) "
            "LIMIT 1",
            (key, key),
        ).fetchone()
        if row is None:
            raise _not_found(f"no product matches: {key}")
        return _product_row_to_dict(conn, row)

    return _read(work)


def add_barcode(product_id, barcode):
    code = str(barcode or "").strip()
    if not code:
        raise _bad("barcode is required")

    def work(conn):
        row = _product_by_product_id(conn, str(product_id).strip())
        _ensure_barcodes_free(conn, [code])
        conn.execute(
            "INSERT INTO product_barcodes (barcode, product_pk) VALUES (?, ?)",
            (code, row["id"]),
        )
        return _product_row_to_dict(conn, row)

    return _tx(work)


# ---------------------------------------------------------------------------
# Suppliers and purchases
# ---------------------------------------------------------------------------

def create_supplier(data):
    _require_dict(data)
    name = _req_text(data, "name")
    phone = _opt_text(data, "phone")
    address = _opt_text(data, "address")

    def work(conn):
        if conn.execute("SELECT 1 FROM suppliers WHERE name = ?", (name,)).fetchone():
            raise _conflict(f"supplier already exists: {name}")
        cur = conn.execute(
            "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
            (name, phone, address),
        )
        return dict(conn.execute(
            "SELECT * FROM suppliers WHERE id = ?", (cur.lastrowid,)
        ).fetchone())

    return _tx(work)


def list_suppliers():
    def work(conn):
        return [dict(r) for r in conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()]

    return _read(work)


def _purchase_dict(conn, purchase_id):
    row = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
    data = dict(row)
    data["items"] = [
        dict(r)
        for r in conn.execute(
            "SELECT pi.id, pi.product_pk, p.product_id, p.name, pi.qty, pi.rate, pi.total "
            "FROM purchase_items pi JOIN products p ON p.id = pi.product_pk "
            "WHERE pi.purchase_id = ? ORDER BY pi.id",
            (purchase_id,),
        ).fetchall()
    ]
    return data


def create_purchase(data):
    _require_dict(data)
    purchase_date = _date_or_today(data, "purchase_date")
    supplier_raw = data.get("supplier_id")
    supplier_no = None if supplier_raw is None else _to_int(supplier_raw, "supplier_id")
    items = _items_list(data)

    parsed = []
    for item in items:
        if not isinstance(item, dict):
            raise _bad("each item must be an object")
        qty = _to_int(item.get("qty"), "qty")
        if qty <= 0:
            raise _bad("qty must be > 0")
        rate = _money_required(item, "rate")
        parsed.append((item, qty, rate))

    amount_paid_raw = data.get("amount_paid")

    def work(conn):
        supplier_pk = None
        if supplier_no is not None:
            supplier = conn.execute(
                "SELECT id FROM suppliers WHERE id = ?", (supplier_no,)
            ).fetchone()
            if supplier is None:
                raise _not_found(f"supplier not found: {supplier_no}")
            supplier_pk = supplier["id"]

        lines = []
        for item, qty, rate in parsed:
            product = _resolve_product(conn, item)
            lines.append((product["id"], product["name"], qty, rate, round(qty * rate, 2)))

        total = round(sum(line[4] for line in lines), 2)
        amount_paid = _money_field({"amount_paid": amount_paid_raw}, "amount_paid", 0)
        if amount_paid > total:
            raise _bad(f"amount_paid ({amount_paid:.2f}) cannot exceed purchase total ({total:.2f})")
        pending = round(total - amount_paid, 2)

        cur = conn.execute(
            "INSERT INTO purchases (purchase_date, supplier_id, total, amount_paid, pending) "
            "VALUES (?, ?, ?, ?, ?)",
            (purchase_date, supplier_pk, total, amount_paid, pending),
        )
        purchase_id = cur.lastrowid
        now = _now()
        for product_pk, _name, qty, rate, line_total in lines:
            conn.execute(
                "INSERT INTO purchase_items (purchase_id, product_pk, qty, rate, total) "
                "VALUES (?, ?, ?, ?, ?)",
                (purchase_id, product_pk, qty, rate, line_total),
            )
            # Latest purchase line wins for the product's costing rate.
            conn.execute(
                "UPDATE products SET stock_qty = stock_qty + ?, purchase_rate = ? WHERE id = ?",
                (qty, rate, product_pk),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_pk, qty_change, reason, reference, created_at) "
                "VALUES (?, ?, 'purchase', ?, ?)",
                (product_pk, qty, f"PUR-{purchase_id}", now),
            )
        return _purchase_dict(conn, purchase_id)

    return _tx(work)


def list_purchases():
    def work(conn):
        ids = [r["id"] for r in conn.execute("SELECT id FROM purchases ORDER BY id").fetchall()]
        return [_purchase_dict(conn, pid) for pid in ids]

    return _read(work)


# ---------------------------------------------------------------------------
# Customers and payments
# ---------------------------------------------------------------------------

def _customer_row(conn, customer_id):
    row = conn.execute(
        "SELECT * FROM customers WHERE customer_id = ?", (str(customer_id).strip(),)
    ).fetchone()
    if row is None:
        raise _not_found(f"customer not found: {customer_id}")
    return row


def create_customer(data):
    _require_dict(data)
    name = _req_text(data, "name")
    requested_id = _opt_text(data, "customer_id")
    phone = _opt_text(data, "phone")
    address = _opt_text(data, "address")
    gstin = _opt_text(data, "gstin")
    credit_limit = _money_field(data, "credit_limit", 0)

    def work(conn):
        if requested_id is None:
            n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM customers").fetchone()["n"]
            customer_id = f"CUST-{n:06d}"
            while conn.execute(
                "SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone():
                n += 1
                customer_id = f"CUST-{n:06d}"
        else:
            customer_id = requested_id
            if conn.execute(
                "SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone():
                raise _conflict(f"customer_id already exists: {customer_id}")
        cur = conn.execute(
            "INSERT INTO customers (customer_id, name, phone, address, gstin, credit_limit) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (customer_id, name, phone, address, gstin, credit_limit),
        )
        return dict(conn.execute(
            "SELECT * FROM customers WHERE id = ?", (cur.lastrowid,)
        ).fetchone())

    return _tx(work)


def search_customers(q):
    key = str(q or "").strip().lower()
    if not key:
        return []
    pattern = f"%{key}%"

    def work(conn):
        rows = conn.execute(
            "SELECT * FROM customers "
            "WHERE lower(name) LIKE ? OR lower(COALESCE(phone, '')) LIKE ? "
            "ORDER BY name LIMIT 20",
            (pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]

    return _read(work)


def list_customers():
    def work(conn):
        return [dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY id").fetchall()]

    return _read(work)


def get_customer(customer_id):
    def work(conn):
        cust = _customer_row(conn, customer_id)
        invoices = [
            dict(r)
            for r in conn.execute(
                "SELECT invoice_no, invoice_date, total_amount, amount_paid, outstanding, status "
                "FROM invoices WHERE customer_pk = ? ORDER BY id",
                (cust["id"],),
            ).fetchall()
        ]
        payments = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM payments WHERE customer_pk = ? ORDER BY id",
                (cust["id"],),
            ).fetchall()
        ]
        total_outstanding = round(sum(inv["outstanding"] for inv in invoices), 2)
        profile = dict(cust)
        profile["invoices"] = invoices
        profile["payments"] = payments
        profile["total_outstanding"] = total_outstanding
        profile["available_credit"] = round(cust["credit_limit"] - total_outstanding, 2)
        return profile

    return _read(work)


def _invoice_row(conn, invoice_no):
    row = conn.execute(
        "SELECT * FROM invoices WHERE invoice_no = ?", (str(invoice_no).strip(),)
    ).fetchone()
    if row is None:
        raise _not_found(f"invoice not found: {invoice_no}")
    return row


def _invoice_dict(conn, invoice_pk):
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_pk,)).fetchone()
    data = dict(row)
    data["items"] = [
        dict(r)
        for r in conn.execute(
            "SELECT ii.id, ii.product_pk, p.product_id, p.name, ii.qty, ii.unit_price, "
            "ii.gst_percent, ii.cost_rate, ii.line_taxable, ii.line_gst, ii.line_total "
            "FROM invoice_items ii JOIN products p ON p.id = ii.product_pk "
            "WHERE ii.invoice_pk = ? ORDER BY ii.id",
            (invoice_pk,),
        ).fetchall()
    ]
    return data


def create_invoice(data):
    _require_dict(data)
    customer_id = _req_text(data, "customer_id")
    payment_type = data.get("payment_type")
    if payment_type not in ("cash", "credit"):
        raise _bad("payment_type must be 'cash' or 'credit'")
    invoice_date = _date_or_today(data, "invoice_date")
    items = _items_list(data)

    requests = []
    for item in items:
        if not isinstance(item, dict):
            raise _bad("each item must be an object")
        qty = _to_int(item.get("qty"), "qty")
        if qty <= 0:
            raise _bad("qty must be > 0")
        requests.append((item, qty))

    def work(conn):
        cust = _customer_row(conn, customer_id)

        # Resolve products and merge duplicate lines for the same product.
        merged = {}
        for item, qty in requests:
            product = _resolve_product(conn, item)
            if product["id"] in merged:
                merged[product["id"]][1] += qty
            else:
                merged[product["id"]] = [product, qty]

        lines = []
        for product, qty in merged.values():
            if qty > product["stock_qty"]:
                raise _conflict(
                    f"insufficient stock for {product['name']} ({product['product_id']}): "
                    f"requested {qty}, available {product['stock_qty']}"
                )
            selling = round(float(product["selling_rate"]), 2)
            gst_percent = float(product["gst_percent"])
            line_taxable = round(qty * selling, 2)
            line_gst = round(line_taxable * gst_percent / 100, 2)
            line_total = round(line_taxable + line_gst, 2)
            lines.append({
                "product": product,
                "qty": qty,
                "unit_price": selling,
                "gst_percent": gst_percent,
                "cost_rate": round(float(product["purchase_rate"]), 2),
                "line_taxable": line_taxable,
                "line_gst": line_gst,
                "line_total": line_total,
            })

        total_taxable = round(sum(l["line_taxable"] for l in lines), 2)
        gst_total = round(sum(l["line_gst"] for l in lines), 2)
        total_amount = round(sum(l["line_total"] for l in lines), 2)

        if payment_type == "credit":
            outstanding_now = round(conn.execute(
                "SELECT COALESCE(SUM(outstanding), 0) AS s FROM invoices WHERE customer_pk = ?",
                (cust["id"],),
            ).fetchone()["s"], 2)
            credit_limit = round(float(cust["credit_limit"]), 2)
            available = round(credit_limit - outstanding_now, 2)
            if total_amount > available:
                raise _conflict(
                    f"credit limit exceeded: credit limit {credit_limit:.2f}, "
                    f"current outstanding {outstanding_now:.2f}, "
                    f"available credit {available:.2f}, "
                    f"invoice total {total_amount:.2f}"
                )
            amount_paid = 0.0
            outstanding = total_amount
            status = "unpaid"
        else:
            amount_paid = total_amount
            outstanding = 0.0
            status = "paid"

        seq = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM invoices").fetchone()["n"]
        invoice_no = f"INV-{seq:06d}"
        cur = conn.execute(
            "INSERT INTO invoices (invoice_no, customer_pk, invoice_date, payment_type, "
            "total_taxable, gst_total, total_amount, amount_paid, outstanding, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice_no, cust["id"], invoice_date, payment_type,
                total_taxable, gst_total, total_amount, amount_paid, outstanding, status,
            ),
        )
        invoice_pk = cur.lastrowid
        now = _now()
        for line in lines:
            product = line["product"]
            conn.execute(
                "INSERT INTO invoice_items (invoice_pk, product_pk, qty, unit_price, gst_percent, "
                "cost_rate, line_taxable, line_gst, line_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice_pk, product["id"], line["qty"], line["unit_price"],
                    line["gst_percent"], line["cost_rate"], line["line_taxable"],
                    line["line_gst"], line["line_total"],
                ),
            )
            conn.execute(
                "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?",
                (line["qty"], product["id"]),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_pk, qty_change, reason, reference, created_at) "
                "VALUES (?, ?, 'sale', ?, ?)",
                (product["id"], -line["qty"], invoice_no, now),
            )

        if payment_type == "cash":
            conn.execute(
                "INSERT INTO payments (customer_pk, invoice_pk, payment_date, amount, note) "
                "VALUES (?, ?, ?, ?, 'cash sale')",
                (cust["id"], invoice_pk, invoice_date, total_amount),
            )
        return _invoice_dict(conn, invoice_pk)

    return _tx(work)


def list_invoices():
    def work(conn):
        ids = [r["id"] for r in conn.execute("SELECT id FROM invoices ORDER BY id").fetchall()]
        return [_invoice_dict(conn, pid) for pid in ids]

    return _read(work)


def get_invoice(invoice_no):
    def work(conn):
        row = _invoice_row(conn, invoice_no)
        return _invoice_dict(conn, row["id"])

    return _read(work)


def record_payment(data):
    _require_dict(data)
    customer_id = _req_text(data, "customer_id")
    invoice_no = _req_text(data, "invoice_no")
    amount = round(_to_number(data.get("amount"), "amount"), 2)
    if amount <= 0:
        raise _bad("amount must be > 0")
    payment_date = _date_or_today(data, "payment_date")
    note = _opt_text(data, "note")

    def work(conn):
        cust = _customer_row(conn, customer_id)
        inv = _invoice_row(conn, invoice_no)
        if inv["customer_pk"] != cust["id"]:
            raise _bad(f"invoice {invoice_no} does not belong to customer {customer_id}")
        outstanding = round(float(inv["outstanding"]), 2)
        if amount > outstanding:
            raise _conflict(
                f"payment {amount:.2f} exceeds outstanding {outstanding:.2f} "
                f"on invoice {invoice_no}"
            )
        new_paid = round(float(inv["amount_paid"]) + amount, 2)
        new_outstanding = round(outstanding - amount, 2)
        if new_outstanding == 0:
            status = "paid"
        elif new_paid > 0:
            status = "partially_paid"
        else:
            status = "unpaid"

        conn.execute(
            "INSERT INTO payments (customer_pk, invoice_pk, payment_date, amount, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (cust["id"], inv["id"], payment_date, amount, note),
        )
        conn.execute(
            "UPDATE invoices SET amount_paid = ?, outstanding = ?, status = ? WHERE id = ?",
            (new_paid, new_outstanding, status, inv["id"]),
        )
        return _invoice_dict(conn, inv["id"])

    return _tx(work)


def list_payments():
    def work(conn):
        return [
            dict(r)
            for r in conn.execute(
                "SELECT p.*, c.customer_id, i.invoice_no "
                "FROM payments p "
                "JOIN customers c ON c.id = p.customer_pk "
                "LEFT JOIN invoices i ON i.id = p.invoice_pk "
                "ORDER BY p.id"
            ).fetchall()
        ]

    return _read(work)


# ---------------------------------------------------------------------------
# Expenses and settings
# ---------------------------------------------------------------------------

_EXPENSE_KINDS = ("fixed", "variable", "other")
_EXPENSE_STATUSES = ("paid", "pending")


def create_expense(data):
    _require_dict(data)
    name = _req_text(data, "name")
    amount = _money_required(data, "amount")
    kind = data.get("kind") or "other"
    if kind not in _EXPENSE_KINDS:
        raise _bad("kind must be one of: fixed, variable, other")
    status = data.get("status") or "pending"
    if status not in _EXPENSE_STATUSES:
        raise _bad("status must be 'paid' or 'pending'")
    expense_date = _date_or_today(data, "expense_date")
    category = _opt_text(data, "category")
    description = _opt_text(data, "description")

    def work(conn):
        cur = conn.execute(
            "INSERT INTO expenses (name, category, kind, amount, expense_date, description, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, category, kind, amount, expense_date, description, status),
        )
        return dict(conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)
        ).fetchone())

    return _tx(work)


def list_expenses():
    def work(conn):
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()]

    return _read(work)


def get_settings():
    def work(conn):
        settings = {
            r["key"]: r["value"]
            for r in conn.execute("SELECT key, value FROM settings").fetchall()
        }
        if "opening_balance" in settings:
            settings["opening_balance"] = float(settings["opening_balance"])
        return settings

    return _read(work)


def set_opening_balance(value):
    number = _to_number(value, "opening_balance")
    if number < 0:
        raise _bad("opening_balance must be >= 0")
    amount = round(number, 2)

    def work(conn):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('opening_balance', ?)",
            (str(amount),),
        )
        return {"opening_balance": amount}

    return _tx(work)
