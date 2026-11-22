"""SQLite connection and schema setup for Just Analyze (stdlib sqlite3 only)."""

import os
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "justanalyze.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    product_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    gst_percent REAL NOT NULL DEFAULT 0,
    hsn_code TEXT,
    billing_id TEXT,
    purchase_date TEXT,
    selling_rate REAL NOT NULL DEFAULT 0,
    purchase_rate REAL NOT NULL DEFAULT 0,
    pre_order_qty INTEGER NOT NULL DEFAULT 0,
    stock_qty INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_barcodes (
    id INTEGER PRIMARY KEY,
    barcode TEXT UNIQUE NOT NULL,
    product_pk INTEGER NOT NULL REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    phone TEXT,
    address TEXT
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY,
    purchase_date TEXT NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id),
    total REAL NOT NULL,
    amount_paid REAL NOT NULL DEFAULT 0,
    pending REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id),
    product_pk INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL,
    rate REAL NOT NULL,
    total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY,
    product_pk INTEGER NOT NULL REFERENCES products(id),
    qty_change INTEGER NOT NULL,
    reason TEXT NOT NULL,
    reference TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    customer_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    gstin TEXT,
    credit_limit REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    invoice_no TEXT UNIQUE NOT NULL,
    customer_pk INTEGER NOT NULL REFERENCES customers(id),
    invoice_date TEXT NOT NULL,
    payment_type TEXT NOT NULL CHECK(payment_type IN ('cash','credit')),
    total_taxable REAL NOT NULL,
    gst_total REAL NOT NULL,
    total_amount REAL NOT NULL,
    amount_paid REAL NOT NULL DEFAULT 0,
    outstanding REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('paid','partially_paid','unpaid'))
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY,
    invoice_pk INTEGER NOT NULL REFERENCES invoices(id),
    product_pk INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    gst_percent REAL NOT NULL,
    cost_rate REAL NOT NULL,
    line_taxable REAL NOT NULL,
    line_gst REAL NOT NULL,
    line_total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    customer_pk INTEGER NOT NULL REFERENCES customers(id),
    invoice_pk INTEGER REFERENCES invoices(id),
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    kind TEXT NOT NULL DEFAULT 'other' CHECK(kind IN ('fixed','variable','other')),
    amount REAL NOT NULL,
    expense_date TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL CHECK(status IN ('paid','pending'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_actions (
    id INTEGER PRIMARY KEY,
    request_key TEXT UNIQUE,
    intent TEXT NOT NULL,
    args_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','confirmed','cancelled','failed')),
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

"""


def _connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn():
    """Return a new connection to the application database."""
    return _connect(DB_PATH)


def init_db(path=None):
    """Create all tables and default settings. Safe to call repeatedly."""
    target = path or DB_PATH
    conn = _connect(target)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('opening_balance', '0')"
        )
    finally:
        conn.close()
